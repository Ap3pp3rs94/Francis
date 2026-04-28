from __future__ import annotations

import json
from pathlib import Path

from francis.governance import approvals
from francis.reactor.deadletters import get_deadletter, list_deadletters
from francis.reactor.events import (
    enqueue_event,
    get_event,
    list_events,
    reactor_review_queue,
    reactor_status,
    record_dispatch_attempt,
)


def _assert_verification(
    event: dict,
    *,
    route: str,
    stable_state: str,
    source_kind: str,
    verification_status: str,
    verification_outcome: str,
) -> dict:
    verification = event["latest_verification_receipt"]
    assert verification["kind"] == "reactor.verification.receipt"
    assert verification["status"] == verification_status
    assert verification["verification_status"] == verification_status
    assert verification["verification_outcome"] == verification_outcome
    assert verification["route"] == route
    assert verification["stable_state"] == stable_state
    assert verification["source_receipt_kind"] == source_kind
    assert verification["verified"] is False
    assert verification["completion_claimed"] is False
    assert verification["completion_claim_allowed"] is False
    assert verification["verification_required_before_completion_claim"] is True
    assert verification["execution_started"] is False
    assert verification["dispatch_applied"] is False
    assert verification["retry_started"] is False
    assert verification["escalation_started"] is False
    assert verification["memory_write"] is False
    assert verification["governance"]["execution_authority"] is False
    assert verification["governance"]["dispatch_authority"] is False
    assert verification["governance"]["approval_authority"] is False
    assert verification["governance"]["retry_authority"] is False
    assert verification["governance"]["deadletter_resolution_authority"] is False
    assert verification["governance"]["memory_write"] is False
    assert event["receipts"][-2]["receipt_id"] == verification["receipt_id"]
    return verification


def _assert_stable_return(
    event: dict,
    *,
    route: str,
    stable_state: str,
    source_kind: str,
    deadletter_enqueued: bool = False,
    retry_candidate: bool = False,
    retry_exhausted: bool = False,
    approval_status: str | None = None,
) -> dict:
    stable_return = event["latest_stable_return"]
    assert stable_return["kind"] == "reactor.stable_return.receipt"
    assert stable_return["status"] == "settled"
    assert stable_return["route"] == route
    assert stable_return["stable_state"] == stable_state
    assert stable_return["source_receipt_kind"] == source_kind
    assert stable_return["returned_to_stable_state"] is True
    assert stable_return["execution_started"] is False
    assert stable_return["dispatch_applied"] is False
    assert stable_return["retry_started"] is False
    assert stable_return["escalation_started"] is False
    assert stable_return["memory_write"] is False
    assert stable_return["governance"]["execution_authority"] is False
    assert stable_return["governance"]["dispatch_authority"] is False
    assert stable_return["governance"]["approval_authority"] is False
    assert stable_return["governance"]["retry_authority"] is False
    assert stable_return["governance"]["deadletter_resolution_authority"] is False
    assert stable_return["governance"]["memory_write"] is False
    assert stable_return.get("deadletter_enqueued", False) is deadletter_enqueued
    assert stable_return.get("retry_candidate", False) is retry_candidate
    assert stable_return.get("retry_exhausted", False) is retry_exhausted
    if approval_status is not None:
        assert stable_return["approval_status"] == approval_status
    verification = event["latest_verification_receipt"]
    assert stable_return["verification_receipt_id"] == verification["receipt_id"]
    assert stable_return["verification_status"] == verification["verification_status"]
    assert stable_return["verification_outcome"] == verification["verification_outcome"]
    assert event["latest_receipt"]["receipt_id"] == stable_return["receipt_id"]
    assert event["receipts"][-1]["receipt_id"] == stable_return["receipt_id"]
    return stable_return


def test_reactor_event_queue_records_bounded_trigger_without_dispatch(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    raw_secret = "api_key=sk-" + ("r" * 24)
    created = enqueue_event(
        {
            "trigger_source": "telemetry_event",
            "trigger_type": "ci_failure",
            "summary": f"CI failed for main {raw_secret}",
            "reason": "main branch CI failure",
            "mode": "assist",
            "risk_tier": "normal",
            "action_class": "classify",
            "trace_id": "trace_ci_1",
            "max_actions": 3,
            "max_runtime_seconds": 120,
            "max_retries": 2,
            "backoff_seconds": 30,
            "stop_conditions": ["classified", "approval_required", "budget_exhausted"],
            "metadata": {"token": raw_secret, "workflow": "ci"},
        }
    )

    assert created["ok"] is True
    assert created["applied"] is True
    event = created["event"]
    assert event["kind"] == "reactor.event"
    assert event["status"] == "queued"
    assert event["trigger"]["source"] == "telemetry_event"
    assert event["trigger"]["summary"] == "CI failed for main api_key=[REDACTED:secret]"
    assert event["trigger"]["metadata"]["token"] == "[REDACTED:secret]"
    assert event["classification"]["dispatch_allowed"] is True
    assert event["bounds"]["max_actions"] == 3
    assert event["bounds"]["max_retries"] == 2
    assert event["dispatch"] == {
        "status": "not_started",
        "allowed": True,
        "applied": False,
        "engine": "not_implemented",
    }
    assert event["governance"]["execution_authority"] is False
    assert event["governance"]["approval_authority"] is False
    assert event["governance"]["dispatch_authority"] is False
    assert event["governance"]["memory_write"] is False

    stored_path = Path(str(event["path"]))
    stored_text = stored_path.read_text(encoding="utf-8")
    assert raw_secret not in stored_text
    stored = json.loads(stored_text)
    assert stored["event_id"] == event["event_id"]

    assert get_event(str(event["event_id"]))["event_id"] == event["event_id"]  # type: ignore[index]
    assert [item["event_id"] for item in list_events(trigger_source="telemetry_event")] == [event["event_id"]]
    status = reactor_status()
    assert status["total"] == 1
    assert status["trigger_source_counts"] == {"telemetry_event": 1}


def test_reactor_event_queue_rejects_invalid_trigger_without_writing(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    rejected = enqueue_event({"trigger_source": "self_loop", "summary": "keep going forever"})

    assert rejected["ok"] is False
    assert rejected["applied"] is False
    assert rejected["error"] == "invalid_trigger_source"
    assert not (data_root / "reactor" / "events").exists()


def test_reactor_dispatch_attempt_records_receipt_without_execution(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    created = enqueue_event(
        {
            "trigger_source": "mission_queue",
            "summary": "Mission queue has a ready item",
            "mode": "pilot",
            "action_class": "mission_tick",
            "max_actions": 2,
            "max_runtime_seconds": 90,
        }
    )
    event_id = str(created["event_id"])

    attempted = record_dispatch_attempt(
        event_id,
        {
            "actor": "reactor.test",
            "reason": "record bounded dispatch attempt before execution engine exists",
        },
    )

    assert attempted["ok"] is True
    assert attempted["applied"] is True
    event = attempted["event"]
    assert event["status"] == "dispatch_deferred"
    assert event["stable_state"] == "awaiting_dispatch_engine"
    assert event["dispatch"]["status"] == "dispatch_deferred"
    assert event["dispatch"]["attempt_count"] == 1
    assert event["dispatch"]["applied"] is False
    assert event["dispatch"]["engine"] == "not_implemented"
    assert event["latest_dispatch_attempt_receipt"]["kind"] == "reactor.dispatch_attempt.receipt"
    assert event["latest_dispatch_attempt_receipt"]["execution_started"] is False
    assert "blocker" not in event["latest_dispatch_attempt_receipt"]
    assert event["latest_dispatch_attempt_receipt"]["budget_snapshot"]["max_actions"] == 2
    _assert_verification(
        event,
        route="dispatch_engine",
        stable_state="awaiting_dispatch_engine",
        source_kind="reactor.dispatch_attempt.receipt",
        verification_status="not_available",
        verification_outcome="dispatch_engine_not_implemented",
    )
    _assert_stable_return(
        event,
        route="dispatch_engine",
        stable_state="awaiting_dispatch_engine",
        source_kind="reactor.dispatch_attempt.receipt",
    )
    assert "blocker" not in event["dispatch"]
    assert "blocked_route" not in event["dispatch"]
    assert "retry_candidate" not in event["dispatch"]
    assert "latest_retry_candidate" not in event
    assert event["governance"]["dispatch_authority"] is False
    assert event["governance"]["execution_authority"] is False
    assert event["governance"]["attempt_only"] is True

    stored = get_event(event_id)
    assert stored is not None
    assert stored["status"] == "dispatch_deferred"
    assert stored["receipts"][-3]["kind"] == "reactor.dispatch_attempt.receipt"
    assert stored["receipts"][-2]["kind"] == "reactor.verification.receipt"
    assert stored["receipts"][-1]["kind"] == "reactor.stable_return.receipt"
    assert stored["decision_journal"][-1]["kind"] == "reactor.dispatch.attempted"
    status = reactor_status()
    assert status["status_counts"] == {"dispatch_deferred": 1}
    assert status["retry_candidate_counts"] == {}
    assert status["verification_counts"] == {"not_available": 1}
    assert status["verification_outcome_counts"] == {"dispatch_engine_not_implemented": 1}
    assert status["stable_return_counts"] == {"settled": 1}


def test_reactor_dispatch_attempt_records_retry_candidate_without_scheduling(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    created = enqueue_event(
        {
            "trigger_source": "mission_queue",
            "summary": "Mission queue item can retry after deferred dispatch",
            "mode": "pilot",
            "action_class": "mission_tick",
            "max_actions": 2,
            "max_runtime_seconds": 90,
            "max_retries": 2,
            "backoff_seconds": 30,
        }
    )
    event_id = str(created["event_id"])

    attempted = record_dispatch_attempt(
        event_id,
        {
            "actor": "reactor.test",
            "reason": "record retry candidate while dispatch engine is absent",
        },
    )

    assert attempted["ok"] is True
    event = attempted["event"]
    assert event["status"] == "dispatch_deferred"
    assert event["stable_state"] == "awaiting_dispatch_engine"
    retry_candidate = event["dispatch"]["retry_candidate"]
    assert retry_candidate["kind"] == "reactor.retry_candidate.receipt"
    assert retry_candidate["status"] == "candidate"
    assert retry_candidate["route"] == "retry_backoff"
    assert retry_candidate["gate"] == "dispatch_engine_not_implemented"
    assert retry_candidate["attempt_count"] == 1
    assert retry_candidate["max_retries"] == 2
    assert retry_candidate["remaining_retries"] == 1
    assert retry_candidate["backoff_seconds"] == 30
    assert retry_candidate["next_retry_after_ts"] >= retry_candidate["ts"] + 30
    assert retry_candidate["retry_scheduled"] is False
    assert retry_candidate["retry_started"] is False
    assert retry_candidate["execution_started"] is False
    assert retry_candidate["applied"] is False
    assert event["latest_retry_candidate"]["candidate_id"] == retry_candidate["candidate_id"]
    _assert_verification(
        event,
        route="retry_backoff",
        stable_state="awaiting_dispatch_engine",
        source_kind="reactor.retry_candidate.receipt",
        verification_status="not_available",
        verification_outcome="retry_scheduler_not_implemented",
    )
    _assert_stable_return(
        event,
        route="retry_backoff",
        stable_state="awaiting_dispatch_engine",
        source_kind="reactor.retry_candidate.receipt",
        retry_candidate=True,
    )
    assert event["latest_dispatch_attempt_receipt"]["kind"] == "reactor.dispatch_attempt.receipt"
    assert event["receipts"][-4]["kind"] == "reactor.dispatch_attempt.receipt"
    assert event["receipts"][-3]["kind"] == "reactor.retry_candidate.receipt"
    assert event["receipts"][-2]["kind"] == "reactor.verification.receipt"
    assert event["receipts"][-1]["kind"] == "reactor.stable_return.receipt"
    assert event["decision_journal"][-1]["retry_candidate_id"] == retry_candidate["candidate_id"]
    assert event["governance"]["dispatch_authority"] is False
    assert event["governance"]["execution_authority"] is False

    stored = get_event(event_id)
    assert stored is not None
    assert stored["latest_retry_candidate"]["candidate_id"] == retry_candidate["candidate_id"]
    status = reactor_status()
    assert status["status_counts"] == {"dispatch_deferred": 1}
    assert status["retry_candidate_counts"] == {"candidate": 1}
    assert status["verification_counts"] == {"not_available": 1}
    assert status["verification_outcome_counts"] == {"retry_scheduler_not_implemented": 1}
    assert status["stable_return_counts"] == {"settled": 1}


def test_reactor_dispatch_attempt_records_retry_exhaustion_and_queues_deadletter(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    created = enqueue_event(
        {
            "trigger_source": "mission_queue",
            "summary": "Mission queue retry budget can be exhausted",
            "mode": "pilot",
            "action_class": "mission_tick",
            "max_actions": 2,
            "max_runtime_seconds": 90,
            "max_retries": 1,
            "backoff_seconds": 15,
        }
    )
    event_id = str(created["event_id"])

    first_attempt = record_dispatch_attempt(
        event_id,
        {
            "actor": "reactor.test",
            "reason": "record first retry candidate",
        },
    )
    assert first_attempt["ok"] is True
    assert first_attempt["event"]["dispatch"]["retry_candidate"]["status"] == "candidate"

    exhausted_attempt = record_dispatch_attempt(
        event_id,
        {
            "actor": "reactor.test",
            "reason": "record retry exhaustion after budget is spent",
        },
    )

    assert exhausted_attempt["ok"] is True
    event = exhausted_attempt["event"]
    assert event["status"] == "dispatch_deferred"
    assert event["stable_state"] == "retry_budget_exhausted"
    assert event["dispatch"]["attempt_count"] == 2
    assert "retry_candidate" not in event["dispatch"]
    retry_exhausted = event["dispatch"]["retry_exhausted"]
    assert retry_exhausted["kind"] == "reactor.retry_exhausted.receipt"
    assert retry_exhausted["status"] == "exhausted"
    assert retry_exhausted["route"] == "deadletter_candidate"
    assert retry_exhausted["gate"] == "retry_budget_exhausted"
    assert retry_exhausted["attempt_count"] == 2
    assert retry_exhausted["max_retries"] == 1
    assert retry_exhausted["remaining_retries"] == 0
    assert retry_exhausted["backoff_seconds"] == 15
    assert retry_exhausted["deadletter_enqueued"] is True
    assert retry_exhausted["retry_scheduled"] is False
    assert retry_exhausted["retry_started"] is False
    assert retry_exhausted["execution_started"] is False
    assert retry_exhausted["applied"] is False
    deadletter_item = event["dispatch"]["deadletter_item"]
    assert deadletter_item["kind"] == "reactor.deadletter.item"
    assert deadletter_item["event_id"] == event_id
    assert deadletter_item["status"] == "queued"
    assert deadletter_item["route"] == "deadletter"
    assert deadletter_item["gate"] == "retry_budget_exhausted"
    assert deadletter_item["source_receipt_kind"] == "reactor.retry_exhausted.receipt"
    assert deadletter_item["execution_started"] is False
    assert deadletter_item["retry_started"] is False
    assert deadletter_item["escalation_started"] is False
    deadletter_enqueue = event["dispatch"]["deadletter_enqueue"]
    assert deadletter_enqueue["kind"] == "reactor.deadletter.enqueue.receipt"
    assert deadletter_enqueue["deadletter_id"] == deadletter_item["deadletter_id"]
    assert deadletter_enqueue["status"] == "queued"
    assert deadletter_enqueue["deadletter_enqueued"] is True
    assert event["latest_retry_exhausted"]["exhaustion_id"] == retry_exhausted["exhaustion_id"]
    assert event["latest_deadletter_item"]["deadletter_id"] == deadletter_item["deadletter_id"]
    assert event["latest_deadletter_enqueue"]["deadletter_id"] == deadletter_item["deadletter_id"]
    _assert_verification(
        event,
        route="deadletter_queue",
        stable_state="retry_budget_exhausted",
        source_kind="reactor.deadletter.enqueue.receipt",
        verification_status="not_run",
        verification_outcome="deadletter_queued_for_review",
    )
    _assert_stable_return(
        event,
        route="deadletter_queue",
        stable_state="retry_budget_exhausted",
        source_kind="reactor.deadletter.enqueue.receipt",
        deadletter_enqueued=True,
        retry_exhausted=True,
    )
    assert event["latest_dispatch_attempt_receipt"]["kind"] == "reactor.dispatch_attempt.receipt"
    assert event["latest_dispatch_attempt_receipt"]["stable_state"] == "retry_budget_exhausted"
    assert (
        event["latest_dispatch_attempt_receipt"]["next_step"]
        == "review_retry_exhaustion_before_deadletter_or_dispatch_engine"
    )
    assert event["receipts"][-5]["kind"] == "reactor.dispatch_attempt.receipt"
    assert event["receipts"][-4]["kind"] == "reactor.retry_exhausted.receipt"
    assert event["receipts"][-3]["kind"] == "reactor.deadletter.enqueue.receipt"
    assert event["receipts"][-2]["kind"] == "reactor.verification.receipt"
    assert event["receipts"][-1]["kind"] == "reactor.stable_return.receipt"
    assert event["decision_journal"][-1]["retry_exhausted_id"] == retry_exhausted["exhaustion_id"]
    assert event["decision_journal"][-1]["deadletter_id"] == deadletter_item["deadletter_id"]
    assert event["decision_journal"][-1]["deadletter_enqueued"] is True
    assert event["governance"]["dispatch_authority"] is False
    assert event["governance"]["execution_authority"] is False
    assert event["governance"]["deadletter_enqueued"] is True
    assert event["governance"]["deadletter_resolution_authority"] is False

    stored = get_event(event_id)
    assert stored is not None
    assert stored["latest_retry_exhausted"]["exhaustion_id"] == retry_exhausted["exhaustion_id"]
    assert get_deadletter(str(deadletter_item["deadletter_id"]))["event_id"] == event_id  # type: ignore[index]
    assert [item["deadletter_id"] for item in list_deadletters()] == [deadletter_item["deadletter_id"]]
    status = reactor_status()
    assert status["status_counts"] == {"dispatch_deferred": 1}
    assert status["stable_state_counts"] == {"retry_budget_exhausted": 1}
    assert status["retry_candidate_counts"] == {}
    assert status["retry_exhausted_counts"] == {"exhausted": 1}
    assert status["deadletter_queue_counts"] == {"queued": 1}
    assert status["deadletter_total"] == 1
    assert status["verification_counts"] == {"not_run": 1}
    assert status["verification_outcome_counts"] == {"deadletter_queued_for_review": 1}
    assert status["stable_return_counts"] == {"settled": 1}


def test_reactor_event_list_filters_review_routes_and_receipt_kinds(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    approval_event = enqueue_event(
        {
            "trigger_source": "user_request",
            "summary": "Approval-gated mutation needs review",
            "risk_tier": "critical",
            "action_class": "mutate",
            "approval_required": True,
            "approval_id": "appr_reactor_filter",
        }
    )
    approval_id = str(approval_event["event_id"])
    record_dispatch_attempt(approval_id, {"actor": "reactor.test"})

    budget_event = enqueue_event(
        {
            "trigger_source": "mission_queue",
            "summary": "Budget-exhausted event needs deadletter review",
            "action_class": "mission_tick",
            "max_actions": 0,
        }
    )
    budget_id = str(budget_event["event_id"])
    record_dispatch_attempt(budget_id, {"actor": "reactor.test"})

    retry_event = enqueue_event(
        {
            "trigger_source": "mission_queue",
            "summary": "Retry-exhausted event needs review",
            "action_class": "mission_tick",
            "max_actions": 1,
            "max_retries": 1,
        }
    )
    retry_id = str(retry_event["event_id"])
    record_dispatch_attempt(retry_id, {"actor": "reactor.test"})
    record_dispatch_attempt(retry_id, {"actor": "reactor.test"})

    assert {item["event_id"] for item in list_events(review_route="approval_queue")} == {approval_id}
    assert {item["event_id"] for item in list_events(blocker_route="deadletter_candidate")} == {budget_id}
    assert {item["event_id"] for item in list_events(review_route="deadletter_candidate")} == {
        budget_id,
        retry_id,
    }
    assert {item["event_id"] for item in list_events(stable_state="retry_budget_exhausted")} == {retry_id}
    assert {item["event_id"] for item in list_events(receipt_kind="reactor.retry_exhausted.receipt")} == {retry_id}
    assert {item["event_id"] for item in list_events(receipt_kind="reactor.verification.receipt")} == {
        approval_id,
        budget_id,
        retry_id,
    }
    assert {item["event_id"] for item in list_events(receipt_kind="reactor.deadletter_candidate.receipt")} == {
        budget_id
    }


def test_reactor_review_queue_projects_active_review_items(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    approval_event = enqueue_event(
        {
            "trigger_source": "user_request",
            "summary": "Approval-gated mutation needs review",
            "risk_tier": "critical",
            "action_class": "mutate",
            "approval_required": True,
            "approval_id": "appr_reactor_review_queue",
        }
    )
    approval_id = str(approval_event["event_id"])
    record_dispatch_attempt(approval_id, {"actor": "reactor.test"})

    mode_event = enqueue_event(
        {
            "trigger_source": "user_request",
            "summary": "Observe mode mutation needs operator review",
            "mode": "observe",
            "action_class": "mutate",
        }
    )
    mode_id = str(mode_event["event_id"])
    record_dispatch_attempt(mode_id, {"actor": "reactor.test"})

    budget_event = enqueue_event(
        {
            "trigger_source": "mission_queue",
            "summary": "Budget-exhausted event needs deadletter review",
            "action_class": "mission_tick",
            "max_actions": 0,
        }
    )
    budget_id = str(budget_event["event_id"])
    record_dispatch_attempt(budget_id, {"actor": "reactor.test"})

    retry_event = enqueue_event(
        {
            "trigger_source": "mission_queue",
            "summary": "Retry candidate needs scheduler review",
            "action_class": "mission_tick",
            "max_actions": 1,
            "max_retries": 2,
        }
    )
    retry_id = str(retry_event["event_id"])
    record_dispatch_attempt(retry_id, {"actor": "reactor.test"})

    exhausted_event = enqueue_event(
        {
            "trigger_source": "mission_queue",
            "summary": "Retry-exhausted event needs deadletter review",
            "action_class": "mission_tick",
            "max_actions": 1,
            "max_retries": 1,
        }
    )
    exhausted_id = str(exhausted_event["event_id"])
    record_dispatch_attempt(exhausted_id, {"actor": "reactor.test"})
    record_dispatch_attempt(exhausted_id, {"actor": "reactor.test"})

    queue = reactor_review_queue()

    assert queue["ok"] is True
    assert queue["available_total"] == 5
    assert queue["route_counts"] == {
        "approval_queue": 1,
        "deadletter_candidate": 2,
        "operator_review": 1,
        "retry_backoff": 1,
    }
    assert queue["governance"]["execution_authority"] is False
    assert queue["governance"]["approval_authority"] is False
    assert queue["governance"]["deadletter_authority"] is False
    assert queue["governance"]["retry_authority"] is False

    by_id = {item["event_id"]: item for item in queue["items"]}
    assert by_id[approval_id]["review"]["route"] == "approval_queue"
    assert by_id[approval_id]["review"]["gate"] == "approval_required"
    assert by_id[approval_id]["trigger"]["approval_id"] == "appr_reactor_review_queue"
    assert by_id[mode_id]["review"]["route"] == "operator_review"
    assert by_id[mode_id]["review"]["action"] == "review_mode_boundary_before_dispatch"
    assert by_id[budget_id]["review"]["receipt_kind"] == "reactor.deadletter_candidate.receipt"
    assert by_id[retry_id]["review"]["route"] == "retry_backoff"
    assert by_id[retry_id]["review"]["receipt_kind"] == "reactor.retry_candidate.receipt"
    assert by_id[exhausted_id]["review"]["route"] == "deadletter_candidate"
    assert by_id[exhausted_id]["review"]["gate"] == "retry_budget_exhausted"
    assert by_id[exhausted_id]["review"]["receipt_kind"] == "reactor.retry_exhausted.receipt"

    deadletter_only = reactor_review_queue(route="deadletter_candidate")

    assert deadletter_only["available_total"] == 2
    assert {item["event_id"] for item in deadletter_only["items"]} == {budget_id, exhausted_id}


def test_reactor_dispatch_attempt_queues_missing_approval_request_once(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    created = enqueue_event(
        {
            "trigger_source": "user_request",
            "summary": "Critical mutation needs a real approval queue handoff",
            "risk_tier": "critical",
            "action_class": "mutate",
            "approval_required": True,
            "mission_id": "msn_reactor_approval",
            "operation_id": "tsk_reactor_approval",
        }
    )
    event_id = str(created["event_id"])

    attempted = record_dispatch_attempt(event_id, {"actor": "reactor.test", "reason": "queue approval"})

    assert attempted["ok"] is True
    event = attempted["event"]
    approval_id = event["trigger"]["approval_id"]
    assert approval_id
    pending_path = data_root / "approvals" / "pending" / f"{approval_id}.json"
    approval_record = json.loads(pending_path.read_text(encoding="utf-8"))
    assert approval_record["action"] == "reactor.dispatch"
    assert approval_record["status"] == "pending"
    assert approval_record["payload"]["kind"] == "reactor.dispatch.approval_request"
    assert approval_record["payload"]["event_id"] == event_id
    assert approval_record["payload"]["mission_id"] == "msn_reactor_approval"
    assert approval_record["payload"]["operation_id"] == "tsk_reactor_approval"
    assert approval_record["payload"]["gate"] == "approval_required"
    assert approval_record["payload"]["route"] == "approval_queue"
    assert approval_record["payload"]["execution_started"] is False
    assert approval_record["payload"]["dispatch_applied"] is False

    approval_request = event["dispatch"]["approval_request"]
    assert approval_request["kind"] == "reactor.approval_request.receipt"
    assert approval_request["approval_id"] == approval_id
    assert approval_request["status"] == "pending"
    assert approval_request["approval_queued"] is True
    assert approval_request["approval_decision_started"] is False
    assert approval_request["execution_started"] is False
    assert approval_request["applied"] is False
    assert event["dispatch"]["blocker"]["approval_id"] == approval_id
    assert event["dispatch"]["blocker"]["approval_request_queued"] is True
    assert event["latest_approval_request"]["approval_id"] == approval_id
    _assert_verification(
        event,
        route="approval_queue",
        stable_state="awaiting_approval",
        source_kind="reactor.approval_request.receipt",
        verification_status="not_run",
        verification_outcome="awaiting_approval",
    )
    _assert_stable_return(
        event,
        route="approval_queue",
        stable_state="awaiting_approval",
        source_kind="reactor.approval_request.receipt",
    )
    assert event["receipts"][-4]["kind"] == "reactor.dispatch_attempt.receipt"
    assert event["receipts"][-3]["kind"] == "reactor.approval_request.receipt"
    assert event["receipts"][-2]["kind"] == "reactor.verification.receipt"
    assert event["receipts"][-1]["kind"] == "reactor.stable_return.receipt"
    assert event["decision_journal"][-1]["approval_id"] == approval_id
    assert event["governance"]["approval_authority"] is False
    assert event["governance"]["approval_request_queued"] is True

    status = reactor_status()
    assert status["blocker_route_counts"] == {"approval_queue": 1}
    assert status["approval_request_counts"] == {"pending": 1}
    review_queue = reactor_review_queue(route="approval_queue")
    assert review_queue["items"][0]["trigger"]["approval_id"] == approval_id
    assert review_queue["items"][0]["review"]["receipt_kind"] == "reactor.approval_request.receipt"
    assert review_queue["items"][0]["review"]["receipt_ref"] == approval_id

    second_attempt = record_dispatch_attempt(event_id, {"actor": "reactor.test", "reason": "queue approval again"})

    assert second_attempt["ok"] is True
    assert second_attempt["event"]["trigger"]["approval_id"] == approval_id
    assert len(list((data_root / "approvals" / "pending").glob("*.json"))) == 1
    assert len(second_attempt["event"]["approval_requests"]) == 1


def test_reactor_dispatch_attempt_resumes_after_approval_without_execution(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    created = enqueue_event(
        {
            "trigger_source": "user_request",
            "summary": "Critical mutation can resume after approval decision",
            "risk_tier": "critical",
            "action_class": "mutate",
            "approval_required": True,
        }
    )
    event_id = str(created["event_id"])

    first_attempt = record_dispatch_attempt(event_id, {"actor": "reactor.test", "reason": "queue approval"})
    approval_id = first_attempt["event"]["trigger"]["approval_id"]
    assert approval_id

    decided = approvals.decide(
        approval_id,
        "approve",
        "approved for bounded Reactor resume",
        actor="operator.test",
    )
    assert decided["ok"] is True
    assert decided["status"] == "approved"

    resumed = record_dispatch_attempt(
        event_id,
        {"actor": "reactor.test", "reason": "resume after approval decision"},
    )

    assert resumed["ok"] is True
    event = resumed["event"]
    assert event["status"] == "dispatch_deferred"
    assert event["stable_state"] == "awaiting_dispatch_engine"
    assert event["dispatch"]["allowed"] is True
    assert event["dispatch"]["applied"] is False
    assert event["dispatch"]["engine"] == "not_implemented"
    assert "blocker" not in event["dispatch"]
    assert "blocked_route" not in event["dispatch"]

    approval_decision = event["dispatch"]["approval_decision"]
    assert approval_decision["kind"] == "reactor.approval_decision.receipt"
    assert approval_decision["approval_id"] == approval_id
    assert approval_decision["status"] == "approved"
    assert approval_decision["approval_allows_dispatch"] is True
    assert approval_decision["approval_decision_recorded"] is True
    assert approval_decision["execution_started"] is False
    assert approval_decision["applied"] is False
    assert event["latest_approval_decision"]["approval_id"] == approval_id
    _assert_verification(
        event,
        route="dispatch_engine",
        stable_state="awaiting_dispatch_engine",
        source_kind="reactor.approval_decision.receipt",
        verification_status="not_available",
        verification_outcome="dispatch_engine_not_implemented",
    )
    _assert_stable_return(
        event,
        route="dispatch_engine",
        stable_state="awaiting_dispatch_engine",
        source_kind="reactor.approval_decision.receipt",
        approval_status="approved",
    )
    assert event["decision_journal"][-1]["approval_status"] == "approved"
    assert event["decision_journal"][-1]["approval_allows_dispatch"] is True
    assert event["governance"]["approval_authority"] is False
    assert event["governance"]["dispatch_authority"] is False
    assert event["governance"]["execution_authority"] is False
    assert event["governance"]["approval_status"] == "approved"
    assert event["governance"]["approval_allows_dispatch"] is True

    status = reactor_status()
    assert status["status_counts"] == {"dispatch_deferred": 1}
    assert status["blocker_route_counts"] == {}
    assert status["approval_decision_counts"] == {"approved": 1}
    assert reactor_review_queue(route="approval_queue")["available_total"] == 0


def test_reactor_dispatch_attempt_blocks_rejected_approval_without_execution(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    created = enqueue_event(
        {
            "trigger_source": "user_request",
            "summary": "Rejected critical mutation stays blocked",
            "risk_tier": "critical",
            "action_class": "mutate",
            "approval_required": True,
        }
    )
    event_id = str(created["event_id"])

    first_attempt = record_dispatch_attempt(event_id, {"actor": "reactor.test", "reason": "queue approval"})
    approval_id = first_attempt["event"]["trigger"]["approval_id"]
    assert approval_id

    decided = approvals.decide(
        approval_id,
        "reject",
        "not approved for dispatch",
        actor="operator.test",
    )
    assert decided["ok"] is True
    assert decided["status"] == "rejected"

    resumed = record_dispatch_attempt(
        event_id,
        {"actor": "reactor.test", "reason": "honor rejected approval decision"},
    )

    assert resumed["ok"] is True
    event = resumed["event"]
    assert event["status"] == "dispatch_blocked"
    assert event["stable_state"] == "approval_rejected"
    assert event["dispatch"]["allowed"] is False
    assert event["dispatch"]["applied"] is False
    assert event["dispatch"]["blocked_route"] == "operator_review"
    assert event["dispatch"]["blocker"]["gate"] == "approval_rejected"
    assert event["dispatch"]["blocker"]["route"] == "operator_review"

    approval_decision = event["dispatch"]["approval_decision"]
    assert approval_decision["kind"] == "reactor.approval_decision.receipt"
    assert approval_decision["approval_id"] == approval_id
    assert approval_decision["status"] == "rejected"
    assert approval_decision["approval_allows_dispatch"] is False
    assert approval_decision["execution_started"] is False
    assert approval_decision["applied"] is False
    _assert_verification(
        event,
        route="operator_review",
        stable_state="approval_rejected",
        source_kind="reactor.approval_decision.receipt",
        verification_status="not_run",
        verification_outcome="approval_denied",
    )
    _assert_stable_return(
        event,
        route="operator_review",
        stable_state="approval_rejected",
        source_kind="reactor.approval_decision.receipt",
        approval_status="rejected",
    )
    assert event["decision_journal"][-1]["approval_status"] == "rejected"
    assert event["decision_journal"][-1]["approval_allows_dispatch"] is False
    assert event["governance"]["approval_authority"] is False
    assert event["governance"]["dispatch_authority"] is False
    assert event["governance"]["execution_authority"] is False
    assert event["governance"]["approval_status"] == "rejected"

    status = reactor_status()
    assert status["status_counts"] == {"dispatch_blocked": 1}
    assert status["blocker_route_counts"] == {"operator_review": 1}
    assert status["approval_decision_counts"] == {"rejected": 1}
    review_queue = reactor_review_queue(route="operator_review")
    assert review_queue["available_total"] == 1
    assert review_queue["items"][0]["review"]["gate"] == "approval_rejected"


def test_reactor_dispatch_attempt_blocks_when_event_requires_approval(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    created = enqueue_event(
        {
            "trigger_source": "user_request",
            "summary": "User requested a critical mutation",
            "risk_tier": "critical",
            "action_class": "mutate",
            "approval_required": True,
            "approval_id": "appr_reactor_mutation",
        }
    )
    event_id = str(created["event_id"])

    attempted = record_dispatch_attempt(event_id, {"actor": "reactor.test"})

    assert attempted["ok"] is True
    event = attempted["event"]
    assert event["status"] == "dispatch_blocked"
    assert event["stable_state"] == "awaiting_approval"
    assert event["dispatch"]["allowed"] is False
    assert event["dispatch"]["applied"] is False
    assert event["dispatch"]["blocked_route"] == "approval_queue"
    assert event["dispatch"]["blocker"]["route"] == "approval_queue"
    assert event["dispatch"]["blocker"]["gate"] == "approval_required"
    assert event["dispatch"]["blocker"]["approval_id"] == "appr_reactor_mutation"
    assert event["dispatch"]["blocker"]["deadletter_candidate"] is False
    assert event["latest_dispatch_attempt_receipt"]["outcome"] == "awaiting_approval"
    assert event["latest_dispatch_attempt_receipt"]["blocker"]["route"] == "approval_queue"
    assert event["latest_dispatch_attempt_receipt"]["next_step"] == "request_or_attach_approval_before_dispatch"
    _assert_verification(
        event,
        route="approval_queue",
        stable_state="awaiting_approval",
        source_kind="reactor.dispatch_attempt.receipt",
        verification_status="not_run",
        verification_outcome="approval_required",
    )
    _assert_stable_return(
        event,
        route="approval_queue",
        stable_state="awaiting_approval",
        source_kind="reactor.dispatch_attempt.receipt",
    )
    assert event["latest_blocker"]["blocker_id"] == event["dispatch"]["blocker"]["blocker_id"]
    assert event["blockers"][-1]["route"] == "approval_queue"
    assert event["governance"]["approval_authority"] is False
    status = reactor_status()
    assert status["stable_state_counts"] == {"awaiting_approval": 1}
    assert status["blocker_route_counts"] == {"approval_queue": 1}


def test_reactor_dispatch_attempt_routes_mode_blocker_to_operator_review(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    created = enqueue_event(
        {
            "trigger_source": "user_request",
            "summary": "Observe mode request cannot mutate",
            "mode": "observe",
            "action_class": "mutate",
        }
    )

    attempted = record_dispatch_attempt(str(created["event_id"]), {"actor": "reactor.test"})

    assert attempted["ok"] is True
    event = attempted["event"]
    assert event["status"] == "dispatch_blocked"
    assert event["stable_state"] == "blocked_by_mode"
    assert event["dispatch"]["blocker"]["route"] == "operator_review"
    assert event["dispatch"]["blocker"]["gate"] == "mode_boundary"
    assert event["dispatch"]["blocker"]["status"] == "waiting_for_mode_change"
    assert event["latest_dispatch_attempt_receipt"]["blocker"]["route"] == "operator_review"
    _assert_verification(
        event,
        route="operator_review",
        stable_state="blocked_by_mode",
        source_kind="reactor.dispatch_attempt.receipt",
        verification_status="not_run",
        verification_outcome="mode_boundary",
    )
    _assert_stable_return(
        event,
        route="operator_review",
        stable_state="blocked_by_mode",
        source_kind="reactor.dispatch_attempt.receipt",
    )
    assert event["decision_journal"][-1]["blocked_route"] == "operator_review"
    assert reactor_status()["blocker_route_counts"] == {"operator_review": 1}


def test_reactor_dispatch_attempt_queues_deadletter_for_exhausted_budget(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    created = enqueue_event(
        {
            "trigger_source": "mission_queue",
            "summary": "Mission queue item has no action budget",
            "action_class": "mission_tick",
            "max_actions": 0,
            "max_retries": 1,
            "backoff_seconds": 15,
        }
    )
    created_event = created["event"]
    assert created_event["bounds"]["max_actions"] == 0
    assert created_event["classification"]["stable_state"] == "blocked_by_budget"

    attempted = record_dispatch_attempt(str(created["event_id"]), {"actor": "reactor.test"})

    assert attempted["ok"] is True
    event = attempted["event"]
    assert event["status"] == "dispatch_blocked"
    assert event["stable_state"] == "blocked_by_budget"
    assert event["dispatch"]["blocker"]["route"] == "deadletter_candidate"
    assert event["dispatch"]["blocker"]["deadletter_candidate"] is True
    assert event["dispatch"]["deadletter_candidate"]["kind"] == "reactor.deadletter_candidate.receipt"
    assert event["dispatch"]["deadletter_candidate"]["status"] == "candidate"
    assert event["dispatch"]["deadletter_candidate"]["deadletter_enqueued"] is True
    assert event["dispatch"]["deadletter_candidate"]["retry_started"] is False
    assert "retry_candidate" not in event["dispatch"]
    assert event["dispatch"]["deadletter_candidate"]["max_actions"] == 0
    assert event["dispatch"]["deadletter_candidate"]["max_retries"] == 1
    deadletter_item = event["dispatch"]["deadletter_item"]
    assert deadletter_item["kind"] == "reactor.deadletter.item"
    assert deadletter_item["event_id"] == str(created["event_id"])
    assert deadletter_item["status"] == "queued"
    assert deadletter_item["route"] == "deadletter"
    assert deadletter_item["gate"] == "budget_exhausted"
    assert deadletter_item["source_receipt_kind"] == "reactor.deadletter_candidate.receipt"
    assert deadletter_item["source_receipt_ref"] == event["dispatch"]["deadletter_candidate"]["candidate_id"]
    assert deadletter_item["execution_started"] is False
    assert deadletter_item["retry_started"] is False
    assert deadletter_item["escalation_started"] is False
    deadletter_enqueue = event["dispatch"]["deadletter_enqueue"]
    assert deadletter_enqueue["kind"] == "reactor.deadletter.enqueue.receipt"
    assert deadletter_enqueue["deadletter_id"] == deadletter_item["deadletter_id"]
    assert deadletter_enqueue["status"] == "queued"
    assert deadletter_enqueue["deadletter_enqueued"] is True
    assert (
        event["latest_deadletter_candidate"]["candidate_id"]
        == event["dispatch"]["deadletter_candidate"]["candidate_id"]
    )
    assert event["latest_deadletter_item"]["deadletter_id"] == deadletter_item["deadletter_id"]
    assert event["latest_deadletter_enqueue"]["deadletter_id"] == deadletter_item["deadletter_id"]
    _assert_verification(
        event,
        route="deadletter_queue",
        stable_state="blocked_by_budget",
        source_kind="reactor.deadletter.enqueue.receipt",
        verification_status="not_run",
        verification_outcome="deadletter_queued_for_review",
    )
    _assert_stable_return(
        event,
        route="deadletter_queue",
        stable_state="blocked_by_budget",
        source_kind="reactor.deadletter.enqueue.receipt",
        deadletter_enqueued=True,
    )
    assert event["latest_dispatch_attempt_receipt"]["kind"] == "reactor.dispatch_attempt.receipt"
    assert (
        event["latest_dispatch_attempt_receipt"]["blocker"]["deadletter_candidate_receipt_id"]
        == event["latest_deadletter_candidate"]["candidate_id"]
    )
    assert event["receipts"][-5]["kind"] == "reactor.dispatch_attempt.receipt"
    assert event["receipts"][-4]["kind"] == "reactor.deadletter_candidate.receipt"
    assert event["receipts"][-3]["kind"] == "reactor.deadletter.enqueue.receipt"
    assert event["receipts"][-2]["kind"] == "reactor.verification.receipt"
    assert event["receipts"][-1]["kind"] == "reactor.stable_return.receipt"
    assert (
        event["decision_journal"][-1]["deadletter_candidate_id"] == event["latest_deadletter_candidate"]["candidate_id"]
    )
    assert event["decision_journal"][-1]["deadletter_id"] == deadletter_item["deadletter_id"]
    assert event["decision_journal"][-1]["deadletter_enqueued"] is True
    assert event["governance"]["deadletter_enqueued"] is True
    assert event["governance"]["deadletter_resolution_authority"] is False
    assert get_deadletter(str(deadletter_item["deadletter_id"]))["event_id"] == str(created["event_id"])  # type: ignore[index]
    assert [item["deadletter_id"] for item in list_deadletters()] == [deadletter_item["deadletter_id"]]

    status = reactor_status()
    assert status["blocker_route_counts"] == {"deadletter_candidate": 1}
    assert status["deadletter_candidate_counts"] == {"candidate": 1}
    assert status["deadletter_queue_counts"] == {"queued": 1}
    assert status["deadletter_total"] == 1
    assert status["verification_counts"] == {"not_run": 1}
    assert status["verification_outcome_counts"] == {"deadletter_queued_for_review": 1}
    assert status["stable_return_counts"] == {"settled": 1}

    second_attempt = record_dispatch_attempt(str(created["event_id"]), {"actor": "reactor.test"})

    assert second_attempt["event"]["dispatch"]["deadletter_enqueue"]["status"] == "already_queued"
    assert len(second_attempt["event"]["deadletter_items"]) == 1
    assert len(list_deadletters()) == 1


def test_reactor_dispatch_attempt_rejects_missing_event(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    missing = record_dispatch_attempt("reactor_evt_missing", {"actor": "reactor.test"})

    assert missing == {"ok": False, "applied": False, "error": "not_found", "event": None}
    assert not (data_root / "reactor" / "events").exists()
