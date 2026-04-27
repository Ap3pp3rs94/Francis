from __future__ import annotations

import json
from pathlib import Path

from francis.reactor.events import (
    enqueue_event,
    get_event,
    list_events,
    reactor_review_queue,
    reactor_status,
    record_dispatch_attempt,
)


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
    assert event["latest_receipt"]["kind"] == "reactor.dispatch_attempt.receipt"
    assert event["latest_receipt"]["execution_started"] is False
    assert "blocker" not in event["latest_receipt"]
    assert event["latest_receipt"]["budget_snapshot"]["max_actions"] == 2
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
    assert stored["receipts"][-1]["kind"] == "reactor.dispatch_attempt.receipt"
    assert stored["decision_journal"][-1]["kind"] == "reactor.dispatch.attempted"
    status = reactor_status()
    assert status["status_counts"] == {"dispatch_deferred": 1}
    assert status["retry_candidate_counts"] == {}


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
    assert event["latest_receipt"]["kind"] == "reactor.retry_candidate.receipt"
    assert event["latest_dispatch_attempt_receipt"]["kind"] == "reactor.dispatch_attempt.receipt"
    assert event["receipts"][-2]["kind"] == "reactor.dispatch_attempt.receipt"
    assert event["receipts"][-1]["kind"] == "reactor.retry_candidate.receipt"
    assert event["decision_journal"][-1]["retry_candidate_id"] == retry_candidate["candidate_id"]
    assert event["governance"]["dispatch_authority"] is False
    assert event["governance"]["execution_authority"] is False

    stored = get_event(event_id)
    assert stored is not None
    assert stored["latest_retry_candidate"]["candidate_id"] == retry_candidate["candidate_id"]
    status = reactor_status()
    assert status["status_counts"] == {"dispatch_deferred": 1}
    assert status["retry_candidate_counts"] == {"candidate": 1}


def test_reactor_dispatch_attempt_records_retry_exhaustion_without_deadlettering(
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
    assert retry_exhausted["deadletter_enqueued"] is False
    assert retry_exhausted["retry_scheduled"] is False
    assert retry_exhausted["retry_started"] is False
    assert retry_exhausted["execution_started"] is False
    assert retry_exhausted["applied"] is False
    assert event["latest_retry_exhausted"]["exhaustion_id"] == retry_exhausted["exhaustion_id"]
    assert event["latest_receipt"]["kind"] == "reactor.retry_exhausted.receipt"
    assert event["latest_dispatch_attempt_receipt"]["kind"] == "reactor.dispatch_attempt.receipt"
    assert event["latest_dispatch_attempt_receipt"]["stable_state"] == "retry_budget_exhausted"
    assert (
        event["latest_dispatch_attempt_receipt"]["next_step"]
        == "review_retry_exhaustion_before_deadletter_or_dispatch_engine"
    )
    assert event["receipts"][-2]["kind"] == "reactor.dispatch_attempt.receipt"
    assert event["receipts"][-1]["kind"] == "reactor.retry_exhausted.receipt"
    assert event["decision_journal"][-1]["retry_exhausted_id"] == retry_exhausted["exhaustion_id"]
    assert event["governance"]["dispatch_authority"] is False
    assert event["governance"]["execution_authority"] is False

    stored = get_event(event_id)
    assert stored is not None
    assert stored["latest_retry_exhausted"]["exhaustion_id"] == retry_exhausted["exhaustion_id"]
    status = reactor_status()
    assert status["status_counts"] == {"dispatch_deferred": 1}
    assert status["stable_state_counts"] == {"retry_budget_exhausted": 1}
    assert status["retry_candidate_counts"] == {}
    assert status["retry_exhausted_counts"] == {"exhausted": 1}


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
    assert event["latest_receipt"]["outcome"] == "awaiting_approval"
    assert event["latest_receipt"]["blocker"]["route"] == "approval_queue"
    assert event["latest_receipt"]["next_step"] == "request_or_attach_approval_before_dispatch"
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
    assert event["latest_receipt"]["blocker"]["route"] == "operator_review"
    assert event["decision_journal"][-1]["blocked_route"] == "operator_review"
    assert reactor_status()["blocker_route_counts"] == {"operator_review": 1}


def test_reactor_dispatch_attempt_records_deadletter_candidate_for_exhausted_budget(
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
    assert event["dispatch"]["deadletter_candidate"]["deadletter_enqueued"] is False
    assert event["dispatch"]["deadletter_candidate"]["retry_started"] is False
    assert "retry_candidate" not in event["dispatch"]
    assert event["dispatch"]["deadletter_candidate"]["max_actions"] == 0
    assert event["dispatch"]["deadletter_candidate"]["max_retries"] == 1
    assert (
        event["latest_deadletter_candidate"]["candidate_id"]
        == event["dispatch"]["deadletter_candidate"]["candidate_id"]
    )
    assert event["latest_receipt"]["kind"] == "reactor.deadletter_candidate.receipt"
    assert event["latest_dispatch_attempt_receipt"]["kind"] == "reactor.dispatch_attempt.receipt"
    assert (
        event["latest_dispatch_attempt_receipt"]["blocker"]["deadletter_candidate_receipt_id"]
        == event["latest_deadletter_candidate"]["candidate_id"]
    )
    assert event["receipts"][-2]["kind"] == "reactor.dispatch_attempt.receipt"
    assert event["receipts"][-1]["kind"] == "reactor.deadletter_candidate.receipt"
    assert (
        event["decision_journal"][-1]["deadletter_candidate_id"] == event["latest_deadletter_candidate"]["candidate_id"]
    )

    status = reactor_status()
    assert status["blocker_route_counts"] == {"deadletter_candidate": 1}
    assert status["deadletter_candidate_counts"] == {"candidate": 1}


def test_reactor_dispatch_attempt_rejects_missing_event(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    missing = record_dispatch_attempt("reactor_evt_missing", {"actor": "reactor.test"})

    assert missing == {"ok": False, "applied": False, "error": "not_found", "event": None}
    assert not (data_root / "reactor" / "events").exists()
