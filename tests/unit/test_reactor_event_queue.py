from __future__ import annotations

import json
from pathlib import Path

from francis.governance import approvals
from francis.missions import store as mission_store
from francis.operations import runtime as operations_runtime
from francis.reactor import dispatch as reactor_dispatch
from francis.reactor.deadletters import (
    get_deadletter,
    get_deadletter_history,
    get_deadletter_recovery_receipt,
    get_external_escalation_delivery,
    get_external_escalation_delivery_processor_readiness,
    get_external_escalation_delivery_sender_readiness,
    list_deadletters,
    list_deadletter_recovery_receipts,
    list_external_escalation_deliveries,
    list_external_escalation_delivery_processor_readiness,
    list_external_escalation_delivery_sender_readiness,
)
from francis.reactor.events import (
    enqueue_event,
    get_event,
    list_approval_resume_history,
    list_events,
    list_proposal_review_history,
    reactor_review_queue,
    reactor_status,
    record_deadletter_escalation_acknowledgement,
    record_deadletter_escalation_handoff,
    record_deadletter_external_escalation_attempt,
    record_deadletter_external_escalation_delivery,
    record_deadletter_external_escalation_delivery_processor_completion,
    record_deadletter_external_escalation_delivery_processor_handoff,
    record_deadletter_external_escalation_delivery_sender_attempt,
    record_deadletter_recovery_request,
    record_deadletter_resolution,
    record_deadletter_review,
    record_dispatch_attempt,
    record_retry_dispatch_attempt,
    record_retry_due,
)
from francis.reactor.external_escalation import (
    external_delivery_sender_preflight,
    external_escalation_adapter_preflight,
)
from francis.reactor.retries import get_retry_schedule, list_retry_schedules


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


def test_external_escalation_adapter_preflight_distinguishes_local_outbox() -> None:
    unknown = external_escalation_adapter_preflight(
        "pager_stub",
        channel="ops_bridge",
        target="on_call",
    )
    assert unknown["external_adapter"] == "pager_stub"
    assert unknown["external_adapter_status"] == "not_configured"
    assert unknown["external_adapter_known"] is False
    assert unknown["external_adapter_configured"] is False
    assert unknown["external_delivery_ready"] is False
    assert unknown["external_delivery_blocker"] == "unsupported_external_adapter"

    local_outbox = external_escalation_adapter_preflight(
        "local-outbox",
        channel="ops_bridge",
        target="on_call",
    )
    assert local_outbox["external_adapter"] == "local_outbox"
    assert local_outbox["external_adapter_status"] == "configured"
    assert local_outbox["external_adapter_known"] is True
    assert local_outbox["external_adapter_configured"] is True
    assert local_outbox["external_delivery_mode"] == "local_outbox"
    assert local_outbox["external_delivery_ready"] is True
    assert local_outbox["external_delivery_queued"] is False
    assert local_outbox["external_delivery_started"] is False


def test_external_delivery_sender_preflight_requires_explicit_sender() -> None:
    missing = external_delivery_sender_preflight(
        "",
        channel="ops_bridge",
        target="on_call",
        processor_completed=True,
    )
    assert missing["external_sender_status"] == "not_configured"
    assert missing["external_sender_ready"] is False
    assert missing["external_sender_blocker"] == "external_sender_adapter_required"
    assert "external_sender_adapter" in missing["missing_requirements"]
    assert missing["external_delivery_started"] is False
    assert missing["external_message_sent"] is False
    assert missing["external_network_send"] is False

    unsupported = external_delivery_sender_preflight(
        "smtp",
        channel="ops_bridge",
        target="on_call",
        processor_completed=True,
    )
    assert unsupported["external_sender_adapter"] == "smtp"
    assert unsupported["external_sender_status"] == "unsupported"
    assert unsupported["external_sender_known"] is False
    assert unsupported["external_sender_configured"] is False
    assert unsupported["external_sender_ready"] is False
    assert unsupported["external_sender_blocker"] == "unsupported_external_sender_adapter"
    assert "supported_external_sender_adapter" in unsupported["missing_requirements"]


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
            "action_class": "classify",
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


def test_reactor_dispatch_engine_blocks_plugin_run_boundary_without_execution(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    created = enqueue_event(
        {
            "trigger_source": "user_request",
            "summary": "Plugin run needs a governed Reactor boundary.",
            "mode": "pilot",
            "action_class": "plugin_run",
            "max_actions": 1,
            "metadata": {"plugin_id": "plugin.reactor.audit"},
        }
    )
    event_id = str(created["event_id"])
    assert created["event"]["classification"]["stable_state"] == "awaiting_dispatch"
    assert created["event"]["classification"]["dispatch_allowed"] is True

    attempted = record_dispatch_attempt(
        event_id,
        {
            "actor": "reactor.test",
            "reason": "prove plugin run dispatch stays blocked until a governed plugin runner exists",
        },
    )

    assert attempted["ok"] is True
    event = attempted["event"]
    assert event["status"] == "dispatch_blocked"
    assert event["stable_state"] == "plugin_run_dispatch_not_enabled"
    assert event["dispatch"]["engine"] == "plugin_run"
    assert event["dispatch"]["applied"] is False
    assert event["dispatch"]["execution_started"] is False
    assert event["dispatch"]["blocked_route"] == "operator_review"
    assert event["governance"]["execution_authority"] is False
    assert event["governance"]["dispatch_authority"] is False
    assert event["governance"]["memory_write"] is False

    execution = event["latest_dispatch_execution_receipt"]
    assert execution["kind"] == "reactor.dispatch.execution.receipt"
    assert execution["status"] == "blocked"
    assert execution["route"] == "plugin_run"
    assert execution["gate"] == "reactor_plugin_run_boundary"
    assert execution["outcome"] == "plugin_run_dispatch_not_enabled"
    assert execution["plugin_id"] == "plugin.reactor.audit"
    assert execution["execution_started"] is False
    assert execution["plugin_execution_started"] is False
    assert execution["dispatch_applied"] is False
    assert execution["readback_only"] is True
    assert execution["governance"]["plugin_run_authority"] is False
    assert execution["governance"]["execution_authority"] is False
    assert execution["governance"]["dispatch_authority"] is False

    _assert_verification(
        event,
        route="operator_review",
        stable_state="plugin_run_dispatch_not_enabled",
        source_kind="reactor.dispatch.execution.receipt",
        verification_status="not_run",
        verification_outcome="plugin_run_dispatch_not_enabled",
    )
    _assert_stable_return(
        event,
        route="operator_review",
        stable_state="plugin_run_dispatch_not_enabled",
        source_kind="reactor.dispatch.execution.receipt",
    )
    assert "retry_candidate" not in event["dispatch"]
    assert "deadletter_candidate" not in event["dispatch"]

    review_queue = reactor_review_queue(route="operator_review")
    assert review_queue["available_total"] == 1
    review = review_queue["items"][0]["review"]
    assert review["gate"] == "plugin_run_dispatch_not_enabled"
    assert review["receipt_kind"] == "reactor.dispatch_blocker"
    assert review["execution_started"] is False
    assert review["applied"] is False
    assert {item["event_id"] for item in list_events(receipt_kind="reactor.dispatch.execution.receipt")} == {event_id}

    status = reactor_status()
    assert status["dispatch_engine_boundary_actions"] == ["execute", "mutate", "plugin_run"]
    assert status["status_counts"] == {"dispatch_blocked": 1}
    assert status["stable_state_counts"] == {"plugin_run_dispatch_not_enabled": 1}
    assert status["dispatch_execution_counts"] == {"blocked": 1}
    assert status["verification_counts"] == {"not_run": 1}
    assert status["verification_outcome_counts"] == {"plugin_run_dispatch_not_enabled": 1}


def test_reactor_dispatch_engine_blocks_execute_boundary_without_execution(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    created = enqueue_event(
        {
            "trigger_source": "user_request",
            "summary": "Generic execute needs a governed Reactor boundary.",
            "mode": "pilot",
            "action_class": "execute",
            "max_actions": 1,
        }
    )
    event_id = str(created["event_id"])
    assert created["event"]["classification"]["stable_state"] == "awaiting_dispatch"
    assert created["event"]["classification"]["dispatch_allowed"] is True

    attempted = record_dispatch_attempt(
        event_id,
        {
            "actor": "reactor.test",
            "reason": "prove generic execute dispatch stays blocked until a governed executor exists",
        },
    )

    assert attempted["ok"] is True
    event = attempted["event"]
    assert event["status"] == "dispatch_blocked"
    assert event["stable_state"] == "execute_dispatch_not_enabled"
    assert event["dispatch"]["engine"] == "execute"
    assert event["dispatch"]["applied"] is False
    assert event["dispatch"]["execution_started"] is False
    assert event["dispatch"]["blocked_route"] == "operator_review"
    assert event["governance"]["execution_authority"] is False
    assert event["governance"]["dispatch_authority"] is False
    assert event["governance"]["memory_write"] is False

    execution = event["latest_dispatch_execution_receipt"]
    assert execution["kind"] == "reactor.dispatch.execution.receipt"
    assert execution["status"] == "blocked"
    assert execution["route"] == "execute"
    assert execution["gate"] == "reactor_execute_boundary"
    assert execution["outcome"] == "execute_dispatch_not_enabled"
    assert execution["execution_started"] is False
    assert execution["dispatch_applied"] is False
    assert execution["readback_only"] is True
    assert execution["governance"]["execute_authority"] is False
    assert execution["governance"]["execution_authority"] is False
    assert execution["governance"]["dispatch_authority"] is False

    _assert_verification(
        event,
        route="operator_review",
        stable_state="execute_dispatch_not_enabled",
        source_kind="reactor.dispatch.execution.receipt",
        verification_status="not_run",
        verification_outcome="execute_dispatch_not_enabled",
    )
    _assert_stable_return(
        event,
        route="operator_review",
        stable_state="execute_dispatch_not_enabled",
        source_kind="reactor.dispatch.execution.receipt",
    )
    assert "retry_candidate" not in event["dispatch"]
    assert "deadletter_candidate" not in event["dispatch"]

    review_queue = reactor_review_queue(route="operator_review")
    assert review_queue["available_total"] == 1
    review = review_queue["items"][0]["review"]
    assert review["gate"] == "execute_dispatch_not_enabled"
    assert review["receipt_kind"] == "reactor.dispatch_blocker"
    assert review["execution_started"] is False
    assert review["applied"] is False
    assert {item["event_id"] for item in list_events(receipt_kind="reactor.dispatch.execution.receipt")} == {event_id}

    status = reactor_status()
    assert status["dispatch_engine_boundary_actions"] == ["execute", "mutate", "plugin_run"]
    assert status["status_counts"] == {"dispatch_blocked": 1}
    assert status["stable_state_counts"] == {"execute_dispatch_not_enabled": 1}
    assert status["dispatch_execution_counts"] == {"blocked": 1}
    assert status["verification_counts"] == {"not_run": 1}
    assert status["verification_outcome_counts"] == {"execute_dispatch_not_enabled": 1}


def test_reactor_dispatch_engine_blocks_mutate_boundary_without_execution(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    created = enqueue_event(
        {
            "trigger_source": "user_request",
            "summary": "Generic mutate needs a governed Reactor boundary.",
            "mode": "pilot",
            "action_class": "mutate",
            "max_actions": 1,
        }
    )
    event_id = str(created["event_id"])
    assert created["event"]["classification"]["stable_state"] == "awaiting_dispatch"
    assert created["event"]["classification"]["dispatch_allowed"] is True

    attempted = record_dispatch_attempt(
        event_id,
        {
            "actor": "reactor.test",
            "reason": "prove generic mutate dispatch stays blocked until a governed mutator exists",
        },
    )

    assert attempted["ok"] is True
    event = attempted["event"]
    assert event["status"] == "dispatch_blocked"
    assert event["stable_state"] == "mutate_dispatch_not_enabled"
    assert event["dispatch"]["engine"] == "mutate"
    assert event["dispatch"]["applied"] is False
    assert event["dispatch"]["execution_started"] is False
    assert event["dispatch"]["blocked_route"] == "operator_review"
    assert event["governance"]["execution_authority"] is False
    assert event["governance"]["dispatch_authority"] is False
    assert event["governance"]["memory_write"] is False

    execution = event["latest_dispatch_execution_receipt"]
    assert execution["kind"] == "reactor.dispatch.execution.receipt"
    assert execution["status"] == "blocked"
    assert execution["route"] == "mutate"
    assert execution["gate"] == "reactor_mutate_boundary"
    assert execution["outcome"] == "mutate_dispatch_not_enabled"
    assert execution["execution_started"] is False
    assert execution["dispatch_applied"] is False
    assert execution["readback_only"] is True
    assert execution["governance"]["mutate_authority"] is False
    assert execution["governance"]["execution_authority"] is False
    assert execution["governance"]["dispatch_authority"] is False

    _assert_verification(
        event,
        route="operator_review",
        stable_state="mutate_dispatch_not_enabled",
        source_kind="reactor.dispatch.execution.receipt",
        verification_status="not_run",
        verification_outcome="mutate_dispatch_not_enabled",
    )
    _assert_stable_return(
        event,
        route="operator_review",
        stable_state="mutate_dispatch_not_enabled",
        source_kind="reactor.dispatch.execution.receipt",
    )
    assert "retry_candidate" not in event["dispatch"]
    assert "deadletter_candidate" not in event["dispatch"]

    review_queue = reactor_review_queue(route="operator_review")
    assert review_queue["available_total"] == 1
    review = review_queue["items"][0]["review"]
    assert review["gate"] == "mutate_dispatch_not_enabled"
    assert review["receipt_kind"] == "reactor.dispatch_blocker"
    assert review["execution_started"] is False
    assert review["applied"] is False
    assert {item["event_id"] for item in list_events(receipt_kind="reactor.dispatch.execution.receipt")} == {event_id}

    status = reactor_status()
    assert status["dispatch_engine_boundary_actions"] == ["execute", "mutate", "plugin_run"]
    assert status["status_counts"] == {"dispatch_blocked": 1}
    assert status["stable_state_counts"] == {"mutate_dispatch_not_enabled": 1}
    assert status["dispatch_execution_counts"] == {"blocked": 1}
    assert status["verification_counts"] == {"not_run": 1}
    assert status["verification_outcome_counts"] == {"mutate_dispatch_not_enabled": 1}


def test_reactor_dispatch_engine_classifies_telemetry_without_execution(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    created = enqueue_event(
        {
            "trigger_source": "telemetry_event",
            "trigger_type": "ci_failure",
            "summary": "CI failed and needs bounded classification",
            "mode": "assist",
            "risk_tier": "normal",
            "max_actions": 2,
            "max_runtime_seconds": 90,
            "metadata": {"workflow": "ci", "secret": "sk-" + ("r" * 24)},
        }
    )
    event_id = str(created["event_id"])

    attempted = record_dispatch_attempt(
        event_id,
        {
            "actor": "reactor.test",
            "reason": "classify telemetry without starting execution",
        },
    )

    assert attempted["ok"] is True
    assert attempted["applied"] is True
    event = attempted["event"]
    assert event["status"] == "dispatch_completed"
    assert event["stable_state"] == "classification_recorded"
    assert event["dispatch"]["status"] == "dispatch_completed"
    assert event["dispatch"]["applied"] is True
    assert event["dispatch"]["engine"] == "classification"
    assert event["dispatch"]["execution_started"] is False
    assert event["governance"]["dispatch_authority"] is True
    assert event["governance"]["execution_authority"] is False
    assert event["governance"]["memory_write"] is False

    execution = event["latest_dispatch_execution_receipt"]
    assert execution["kind"] == "reactor.dispatch.execution.receipt"
    assert execution["route"] == "classification"
    assert execution["outcome"] == "telemetry_event_classified"
    assert execution["trigger_source"] == "telemetry_event"
    assert execution["trigger_type"] == "ci_failure"
    assert execution["metadata_keys"] == ["secret", "workflow"]
    assert execution["execution_started"] is False
    assert execution["dispatch_applied"] is True
    assert execution["verified"] is True
    assert execution["readback_only"] is True
    assert execution["memory_write"] is False
    assert execution["governance"]["classification_authority"] is True
    assert execution["governance"]["execution_authority"] is False

    verification = event["latest_verification_receipt"]
    assert verification["verification_status"] == "passed"
    assert verification["verification_outcome"] == "telemetry_event_classified"
    assert verification["verification_reason"] == "classification_completed_with_execution_receipts"
    assert verification["route"] == "classification"
    assert verification["execution_started"] is False
    assert verification["dispatch_applied"] is True
    assert verification["governance"]["execution_authority"] is False

    stable_return = event["latest_stable_return"]
    assert stable_return["route"] == "classification"
    assert stable_return["stable_state"] == "classification_recorded"
    assert stable_return["source_receipt_kind"] == "reactor.dispatch.execution.receipt"
    assert stable_return["execution_started"] is False
    assert stable_return["dispatch_applied"] is True

    stored_text = Path(str(event["path"])).read_text(encoding="utf-8")
    assert "sk-" + ("r" * 24) not in stored_text
    status = reactor_status()
    assert status["dispatch_engine_supported_actions"] == [
        "classify",
        "mission_tick",
        "operation_run",
        "proposal_review",
        "resume",
    ]
    assert status["status_counts"] == {"dispatch_completed": 1}
    assert status["dispatch_execution_counts"] == {"completed": 1}
    assert status["verification_counts"] == {"passed": 1}
    assert status["verification_outcome_counts"] == {"telemetry_event_classified": 1}


def test_reactor_dispatch_engine_records_approval_resume_without_execution(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    blocked = enqueue_event(
        {
            "trigger_source": "user_request",
            "summary": "Critical mutation needs approval before dispatch",
            "risk_tier": "critical",
            "action_class": "mutate",
            "approval_required": True,
            "operation_id": "op_resume_unit",
        }
    )
    target_event_id = str(blocked["event_id"])
    first_attempt = record_dispatch_attempt(target_event_id, {"actor": "reactor.test", "reason": "queue approval"})
    approval_id = first_attempt["event"]["trigger"]["approval_id"]
    decided = approvals.decide(
        approval_id,
        "approve",
        "approved for bounded Reactor resume record",
        actor="operator.test",
    )
    assert decided["ok"] is True
    assert decided["status"] == "approved"

    created_resume = enqueue_event(
        {
            "trigger_source": "approval_decision",
            "trigger_type": "approved",
            "summary": "Approval decision can resume Reactor work",
            "approval_id": approval_id,
            "metadata": {
                "reactor_event_id": target_event_id,
                "operation_id": "op_resume_unit",
            },
        }
    )
    resume_event_id = str(created_resume["event_id"])
    assert created_resume["event"]["classification"]["action_class"] == "resume"

    resumed = record_dispatch_attempt(
        resume_event_id,
        {
            "actor": "reactor.test",
            "reason": "record approval resume without executing target event",
        },
    )

    assert resumed["ok"] is True
    event = resumed["event"]
    assert event["status"] == "dispatch_completed"
    assert event["stable_state"] == "approval_resume_recorded"
    assert event["dispatch"]["engine"] == "approval_resume"
    assert event["dispatch"]["applied"] is True
    assert event["dispatch"]["execution_started"] is False
    assert event["governance"]["dispatch_authority"] is True
    assert event["governance"]["execution_authority"] is False
    assert event["governance"]["approval_authority"] is False

    execution = event["latest_dispatch_execution_receipt"]
    assert execution["kind"] == "reactor.dispatch.execution.receipt"
    assert execution["route"] == "approval_resume"
    assert execution["outcome"] == "approval_resume_approved"
    assert execution["approval_id"] == approval_id
    assert execution["approval_status"] == "approved"
    assert execution["approval_allows_dispatch"] is True
    assert execution["target_event_id"] == target_event_id
    assert execution["operation_id"] == "op_resume_unit"
    assert execution["execution_started"] is False
    assert execution["dispatch_applied"] is True
    assert execution["approval_decision_applied"] is False
    assert execution["readback_only"] is True
    assert execution["memory_write"] is False
    assert execution["governance"]["approval_decision_authority"] is False
    assert execution["governance"]["execution_authority"] is False

    verification = event["latest_verification_receipt"]
    assert verification["verification_status"] == "passed"
    assert verification["verification_outcome"] == "approval_resume_approved"
    assert verification["verification_reason"] == "approval_resume_completed_with_execution_receipts"
    assert verification["route"] == "approval_resume"
    assert verification["execution_started"] is False
    assert verification["dispatch_applied"] is True

    stable_return = event["latest_stable_return"]
    assert stable_return["route"] == "approval_resume"
    assert stable_return["stable_state"] == "approval_resume_recorded"
    assert stable_return["execution_started"] is False
    assert stable_return["dispatch_applied"] is True

    target_event = get_event(target_event_id)
    assert target_event is not None
    assert target_event["status"] == "dispatch_blocked"
    assert target_event["dispatch"]["applied"] is False
    assert "dispatch_execution_receipt" not in target_event["dispatch"]

    status = reactor_status()
    assert status["dispatch_engine_supported_actions"] == [
        "classify",
        "mission_tick",
        "operation_run",
        "proposal_review",
        "resume",
    ]
    assert status["status_counts"] == {"dispatch_blocked": 1, "dispatch_completed": 1}
    assert status["dispatch_execution_counts"] == {"completed": 1}
    assert status["verification_counts"] == {"not_run": 1, "passed": 1}
    assert status["verification_outcome_counts"] == {"approval_resume_approved": 1, "awaiting_approval": 1}

    history = list_approval_resume_history(approval_id=approval_id)
    assert len(history) == 1
    history_item = history[0]
    assert history_item["kind"] == "reactor.approval_resume.history.readback"
    assert history_item["event_id"] == resume_event_id
    assert history_item["route"] == "approval_resume"
    assert history_item["outcome"] == "approval_resume_approved"
    assert history_item["approval_id"] == approval_id
    assert history_item["approval_status"] == "approved"
    assert history_item["approval_allows_dispatch"] is True
    assert history_item["target_event_id"] == target_event_id
    assert history_item["operation_id"] == "op_resume_unit"
    assert history_item["execution_started"] is False
    assert history_item["approval_decision_applied"] is False
    assert history_item["governance"]["approval_decision_authority"] is False
    assert history_item["governance"]["execution_authority"] is False
    assert list_approval_resume_history(approval_status="approved")[0]["event_id"] == resume_event_id
    assert list_approval_resume_history(target_event_id=target_event_id)[0]["event_id"] == resume_event_id
    assert list_approval_resume_history(operation_id="op_resume_unit")[0]["event_id"] == resume_event_id
    assert list_approval_resume_history(approval_allows_dispatch=True)[0]["event_id"] == resume_event_id
    assert list_approval_resume_history(approval_id="missing_approval") == []


def test_reactor_dispatch_engine_runs_existing_operation_with_receipts(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    actor = "test.reactor.dispatch"
    monkeypatch.setenv("FRANCIS_API_ACTOR_SCOPES", json.dumps({actor: ["operations.run"]}))

    created_operation = operations_runtime.create_operation(
        action="plan.create",
        reason="reactor dispatch should run an existing operation",
        input={"goal": "prove reactor operation dispatch"},
        actor=actor,
    )
    assert created_operation["ok"] is True
    operation_id = str(created_operation["operation_id"])

    created_event = enqueue_event(
        {
            "trigger_source": "mission_queue",
            "summary": "Reactor can run the linked operation once.",
            "mode": "pilot",
            "action_class": "operation_run",
            "operation_id": operation_id,
            "max_actions": 1,
        }
    )
    event_id = str(created_event["event_id"])

    dispatched = record_dispatch_attempt(
        event_id,
        {"actor": actor, "reason": "run linked operation through the bounded dispatch engine"},
    )

    assert dispatched["ok"] is True
    event = dispatched["event"]
    assert event["status"] == "dispatch_completed"
    assert event["stable_state"] == "dispatch_succeeded"
    assert event["dispatch"]["engine"] == "operation_run"
    assert event["dispatch"]["applied"] is True
    assert event["dispatch"]["execution_started"] is True
    execution_receipt = event["latest_dispatch_execution_receipt"]
    assert execution_receipt["kind"] == "reactor.dispatch.execution.receipt"
    assert execution_receipt["status"] == "completed"
    assert execution_receipt["outcome"] == "operation_succeeded"
    assert execution_receipt["operation_id"] == operation_id
    assert execution_receipt["operation_status"] == "succeeded"
    assert execution_receipt["execution_started"] is True
    assert execution_receipt["dispatch_applied"] is True
    assert execution_receipt["verified"] is True
    assert execution_receipt["completion_claim_allowed"] is True
    assert execution_receipt["governance"]["authority_source"] == "operations.run"
    assert execution_receipt["governance"]["approval_authority"] is False
    assert execution_receipt["governance"]["memory_write"] is False
    assert str(execution_receipt["trace_id"]).startswith("trace_")
    assert str(execution_receipt["run_id"]).startswith("run_")

    dispatch_receipt = event["latest_dispatch_attempt_receipt"]
    assert dispatch_receipt["status"] == "dispatch_completed"
    assert dispatch_receipt["engine"] == "operation_run"
    assert dispatch_receipt["applied"] is True
    assert dispatch_receipt["execution_started"] is True
    assert dispatch_receipt["operation_id"] == operation_id

    verification = event["latest_verification_receipt"]
    assert verification["verification_status"] == "passed"
    assert verification["verification_outcome"] == "operation_succeeded"
    assert verification["source_receipt_kind"] == "reactor.dispatch.execution.receipt"
    assert verification["verified"] is True
    assert verification["completion_claimed"] is True
    assert verification["completion_claim_allowed"] is True
    assert verification["operation_id"] == operation_id
    assert verification["execution_started"] is True
    assert verification["dispatch_applied"] is True
    assert verification["governance"]["execution_authority"] is True
    assert verification["governance"]["approval_authority"] is False
    assert verification["governance"]["memory_write"] is False

    stable_return = event["latest_stable_return"]
    assert stable_return["route"] == "operation_run"
    assert stable_return["stable_state"] == "dispatch_succeeded"
    assert stable_return["source_receipt_kind"] == "reactor.dispatch.execution.receipt"
    assert stable_return["execution_started"] is True
    assert stable_return["dispatch_applied"] is True
    assert stable_return["governance"]["execution_authority"] is True
    assert stable_return["governance"]["approval_authority"] is False

    by_receipt = list_events(receipt_kind="reactor.dispatch.execution.receipt")
    assert [item["event_id"] for item in by_receipt] == [event_id]
    by_state = list_events(stable_state="dispatch_succeeded")
    assert [item["event_id"] for item in by_state] == [event_id]
    status = reactor_status()
    assert status["status_counts"] == {"dispatch_completed": 1}
    assert status["dispatch_execution_counts"] == {"completed": 1}
    assert status["verification_counts"] == {"passed": 1}
    assert status["verification_outcome_counts"] == {"operation_succeeded": 1}

    operation_detail = operations_runtime.get_operation_detail(operation_id)
    assert operation_detail["operation"]["status"] == "succeeded"


def test_reactor_proposal_review_history_readback_is_read_only(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    actor = "test.reactor.proposal_review"
    monkeypatch.setenv("FRANCIS_API_ACTOR_SCOPES", json.dumps({actor: ["reactor.write"]}))
    proposal_id = "plugin_proposal_history_unit"
    proposal_path = data_root / "artifacts" / "plugins" / "proposals" / f"{proposal_id}.json"
    proposal_path.parent.mkdir(parents=True, exist_ok=True)
    proposal_path.write_text(
        json.dumps(
            {
                "kind": "plugin.proposal",
                "proposal_id": proposal_id,
                "plugin_id": "generated.proposal_history_unit",
                "status": "staged",
                "friction": {
                    "summary": "Repeated proposal reviews need direct Reactor history.",
                    "evidence": ["forge.proposal.history.unit"],
                },
                "quality_requirements": {
                    "tests": ["tests/unit/test_reactor_event_queue.py::proposal_history"],
                    "docs": ["README.md"],
                    "risk_tier": "normal",
                    "validation_path": ["tests/unit/test_reactor_event_queue.py"],
                    "known_limits": ["readback only"],
                },
                "review": {"status": "approved", "receipt_id": "review_history_unit"},
                "validation": {"validation_receipt_id": "validation_history_unit"},
            }
        ),
        encoding="utf-8",
    )
    created_event = enqueue_event(
        {
            "trigger_source": "forge_proposal",
            "summary": "Inspect proposal history through Reactor.",
            "mode": "pilot",
            "actor": actor,
            "max_actions": 1,
            "metadata": {"proposal_id": proposal_id},
        }
    )
    event_id = str(created_event["event_id"])

    dispatched = record_dispatch_attempt(
        event_id,
        {"actor": actor, "reason": "read proposal quality history without changing proposal state"},
    )

    assert dispatched["ok"] is True
    history = list_proposal_review_history(proposal_id=proposal_id)
    assert [item["event_id"] for item in history] == [event_id]
    item = history[0]
    assert item["kind"] == "reactor.proposal_review.history.readback"
    assert item["proposal_id"] == proposal_id
    assert item["plugin_id"] == "generated.proposal_history_unit"
    assert item["route"] == "proposal_review"
    assert item["quality_ready"] is True
    assert item["review_status"] == "approved"
    assert item["review_receipt_id"] == "review_history_unit"
    assert item["validation_receipt_id"] == "validation_history_unit"
    assert item["readback_only"] is True
    assert item["proposal_decision_applied"] is False
    assert item["promotion_applied"] is False
    assert item["execution_started"] is False
    assert item["dispatch_applied"] is True
    assert item["memory_write"] is False
    assert item["source_governance"]["dispatch_authority"] is True
    assert item["governance"]["execution_authority"] is False
    assert item["governance"]["dispatch_authority"] is False
    assert item["governance"]["proposal_decision_authority"] is False
    assert item["governance"]["promotion_authority"] is False
    assert list_proposal_review_history(plugin_id="generated.proposal_history_unit")[0]["event_id"] == event_id
    assert list_proposal_review_history(quality_ready=True)[0]["event_id"] == event_id
    assert list_proposal_review_history(review_status="approved")[0]["event_id"] == event_id
    assert list_proposal_review_history(proposal_id="missing_proposal") == []


def test_reactor_dispatch_engine_runs_mission_tick_with_receipts(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    actor = "test.reactor.mission_tick"
    monkeypatch.setenv("FRANCIS_API_ACTOR_SCOPES", json.dumps({actor: ["missions.write"]}))

    mission, error = mission_store.create_mission(
        mission_store.MissionCreateRequest(
            objective="advance one mission through reactor mission tick",
            requester_id=actor,
            summary="Mission tick dispatch proof",
        )
    )
    assert error is None
    assert mission is not None

    created_event = enqueue_event(
        {
            "trigger_source": "mission_queue",
            "summary": "Reactor can advance one mission queue item once.",
            "mode": "pilot",
            "action_class": "mission_tick",
            "max_actions": 1,
        }
    )
    event_id = str(created_event["event_id"])

    dispatched = record_dispatch_attempt(
        event_id,
        {"actor": actor, "reason": "run one bounded mission queue tick through the dispatch engine"},
    )

    assert dispatched["ok"] is True
    event = dispatched["event"]
    assert event["status"] == "dispatch_completed"
    assert event["stable_state"] == "dispatch_succeeded"
    assert event["dispatch"]["engine"] == "mission_tick"
    assert event["dispatch"]["applied"] is True
    assert event["dispatch"]["execution_started"] is True
    execution_receipt = event["latest_dispatch_execution_receipt"]
    assert execution_receipt["kind"] == "reactor.dispatch.execution.receipt"
    assert execution_receipt["status"] == "completed"
    assert execution_receipt["outcome"] == "mission_tick_succeeded"
    assert execution_receipt["route"] == "mission_tick"
    assert execution_receipt["mission_queue_limit"] == 1
    assert execution_receipt["mission_queue_processed"] >= 1
    assert execution_receipt["mission_queue_applied"] >= 1
    assert execution_receipt["mission_queue_advanced"] >= 1
    assert execution_receipt["mission_queue_error_count"] == 0
    assert mission.mission_id in execution_receipt["mission_ids"]
    assert execution_receipt["operation_ids"]
    assert execution_receipt["execution_started"] is True
    assert execution_receipt["dispatch_applied"] is True
    assert execution_receipt["verified"] is True
    assert execution_receipt["completion_claim_allowed"] is True
    assert execution_receipt["memory_write"] is False
    assert execution_receipt["governance"]["authority_source"] == "missions.write"
    assert execution_receipt["governance"]["approval_authority"] is False
    assert execution_receipt["governance"]["memory_write"] is False

    dispatch_receipt = event["latest_dispatch_attempt_receipt"]
    assert dispatch_receipt["status"] == "dispatch_completed"
    assert dispatch_receipt["engine"] == "mission_tick"
    assert dispatch_receipt["applied"] is True
    assert dispatch_receipt["execution_started"] is True

    verification = event["latest_verification_receipt"]
    assert verification["verification_status"] == "passed"
    assert verification["verification_outcome"] == "mission_tick_succeeded"
    assert verification["verification_reason"] == "mission_tick_completed_with_execution_receipts"
    assert verification["route"] == "mission_tick"
    assert verification["source_receipt_kind"] == "reactor.dispatch.execution.receipt"
    assert verification["verified"] is True
    assert verification["completion_claimed"] is True
    assert verification["completion_claim_allowed"] is True
    assert verification["execution_started"] is True
    assert verification["dispatch_applied"] is True
    assert verification["governance"]["execution_authority"] is True
    assert verification["governance"]["approval_authority"] is False
    assert verification["governance"]["memory_write"] is False

    stable_return = event["latest_stable_return"]
    assert stable_return["route"] == "mission_tick"
    assert stable_return["stable_state"] == "dispatch_succeeded"
    assert stable_return["source_receipt_kind"] == "reactor.dispatch.execution.receipt"
    assert stable_return["execution_started"] is True
    assert stable_return["dispatch_applied"] is True
    assert stable_return["governance"]["execution_authority"] is True
    assert stable_return["governance"]["approval_authority"] is False

    status = reactor_status()
    assert status["dispatch_engine_supported_actions"] == [
        "classify",
        "mission_tick",
        "operation_run",
        "proposal_review",
        "resume",
    ]
    assert status["status_counts"] == {"dispatch_completed": 1}
    assert status["dispatch_execution_counts"] == {"completed": 1}
    assert status["verification_counts"] == {"passed": 1}
    assert status["verification_outcome_counts"] == {"mission_tick_succeeded": 1}


def test_reactor_failed_mission_tick_dispatch_schedules_retry_then_deadletters(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    actor = "test.reactor.mission_tick"
    monkeypatch.setenv("FRANCIS_API_ACTOR_SCOPES", json.dumps({actor: ["missions.write"]}))

    run_calls: list[int] = []

    def fail_mission_tick(*, limit: int, actor: str, note: str) -> dict[str, object]:
        run_calls.append(limit)
        return {
            "ok": False,
            "status": "failed",
            "processed": 1,
            "total": 1,
            "applied": 0,
            "advanced": 0,
            "counts": {"queued": 1, "active": 0, "blocked": 0, "failed": 0, "deadlettered": 0},
            "errors": [{"mission_id": "msn_failed_tick", "error": "synthetic mission tick failure"}],
            "request": {"actor": actor, "note": note, "limit": limit},
        }

    monkeypatch.setattr(reactor_dispatch.mission_runtime, "run_queue_once", fail_mission_tick)

    created_event = enqueue_event(
        {
            "trigger_source": "mission_queue",
            "summary": "Reactor retries a failed mission queue tick.",
            "mode": "pilot",
            "action_class": "mission_tick",
            "max_actions": 2,
            "max_retries": 1,
            "backoff_seconds": 0,
        }
    )
    event_id = str(created_event["event_id"])

    dispatched = record_dispatch_attempt(
        event_id,
        {"actor": actor, "reason": "run mission tick and preserve failure retry route"},
    )

    assert dispatched["ok"] is True
    event = dispatched["event"]
    assert event["status"] == "dispatch_failed"
    assert event["stable_state"] == "awaiting_retry"
    assert event["dispatch"]["engine"] == "mission_tick"
    assert event["dispatch"]["applied"] is True
    assert event["dispatch"]["execution_started"] is True
    assert run_calls == [2]
    execution = event["latest_dispatch_execution_receipt"]
    assert execution["status"] == "failed"
    assert execution["outcome"] == "mission_tick_failed"
    assert execution["route"] == "mission_tick"
    assert execution["mission_queue_error_count"] == 1
    assert execution["verified"] is False
    retry_candidate = event["latest_retry_candidate"]
    assert retry_candidate["gate"] == "mission_tick_failed"
    assert retry_candidate["outcome"] == "mission_tick_failed"
    assert retry_candidate["stable_state"] == "awaiting_retry"
    assert retry_candidate["execution_started"] is True
    assert retry_candidate["retry_scheduled"] is True
    retry_schedule = event["latest_retry_schedule"]
    retry_schedule_id = str(retry_schedule["retry_schedule_id"])
    assert retry_schedule["status"] == "scheduled"
    assert retry_schedule["gate"] == "mission_tick_failed"
    verification = event["latest_verification_receipt"]
    assert verification["verification_status"] == "failed"
    assert verification["verification_outcome"] == "mission_tick_failed"
    assert verification["route"] == "retry_backoff"
    assert verification["source_receipt_kind"] == "reactor.retry.schedule.receipt"
    assert verification["completion_claim_allowed"] is False
    stable_return = event["latest_stable_return"]
    assert stable_return["route"] == "retry_backoff"
    assert stable_return["stable_state"] == "awaiting_retry"
    assert stable_return["source_receipt_kind"] == "reactor.retry.schedule.receipt"
    assert stable_return["retry_scheduled"] is True

    due = record_retry_due(retry_schedule_id, {"actor": actor, "reason": "make failed mission tick retry due"})
    assert due["status"] == "retry_due"

    retry_attempt = record_retry_dispatch_attempt(
        retry_schedule_id,
        {
            "actor": actor,
            "reason": "retry failed mission tick and exhaust retry budget",
        },
    )

    assert retry_attempt["ok"] is True
    assert retry_attempt["status"] == "retry_dispatch_attempted"
    event = retry_attempt["event"]
    assert event["status"] == "dispatch_failed"
    assert event["stable_state"] == "retry_budget_exhausted"
    assert event["dispatch"]["engine"] == "mission_tick"
    assert event["dispatch"]["applied"] is True
    assert event["dispatch"]["execution_started"] is True
    assert run_calls == [2, 2]
    execution = event["latest_dispatch_execution_receipt"]
    assert execution["status"] == "failed"
    assert execution["outcome"] == "mission_tick_failed"
    assert execution["route"] == "mission_tick"
    assert execution["attempt_count"] == 2
    assert execution["mission_queue_error_count"] == 1
    assert execution["verified"] is False
    retry_exhausted = event["latest_retry_exhausted"]
    assert retry_exhausted["kind"] == "reactor.retry_exhausted.receipt"
    assert retry_exhausted["outcome"] == "mission_tick_failed"
    assert retry_exhausted["execution_started"] is True
    assert retry_exhausted["attempt_count"] == 2
    assert retry_exhausted["deadletter_enqueued"] is True
    deadletter_item = event["latest_deadletter_item"]
    assert deadletter_item["source_receipt_kind"] == "reactor.retry_exhausted.receipt"
    assert deadletter_item["gate"] == "retry_budget_exhausted"
    assert deadletter_item["status"] == "queued"
    deadletter_enqueue = event["latest_deadletter_enqueue"]
    assert deadletter_enqueue["source_receipt_kind"] == "reactor.retry_exhausted.receipt"
    assert event["latest_stable_return"]["route"] == "deadletter_queue"
    assert event["latest_stable_return"]["deadletter_enqueued"] is True
    assert event["latest_stable_return"]["retry_exhausted"] is True
    assert event["latest_verification_receipt"]["verification_status"] == "failed"
    assert event["latest_verification_receipt"]["verification_outcome"] == "mission_tick_failed"
    assert event["latest_verification_receipt"]["route"] == "deadletter_queue"
    assert event["latest_verification_receipt"]["completion_claim_allowed"] is False
    assert get_deadletter(str(deadletter_item["deadletter_id"]))["event_id"] == event_id  # type: ignore[index]
    status = reactor_status()
    assert status["status_counts"] == {"dispatch_failed": 1}
    assert status["stable_state_counts"] == {"retry_budget_exhausted": 1}
    assert status["dispatch_execution_counts"] == {"failed": 1}
    assert status["retry_schedule_counts"] == {"attempted": 1}
    assert status["retry_dispatch_attempt_counts"] == {"attempted": 1}
    assert status["retry_exhausted_counts"] == {"exhausted": 1}
    assert status["deadletter_queue_counts"] == {"queued": 1}


def test_reactor_dispatch_engine_blocks_mission_tick_without_missions_scope(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    actor = "test.reactor.mission_tick"
    monkeypatch.setenv("FRANCIS_API_ACTOR_SCOPES", json.dumps({actor: ["reactor.write"]}))

    mission, error = mission_store.create_mission(
        mission_store.MissionCreateRequest(
            objective="do not advance without mission write scope",
            requester_id=actor,
            summary="Mission tick permission proof",
        )
    )
    assert error is None
    assert mission is not None

    created_event = enqueue_event(
        {
            "trigger_source": "mission_queue",
            "summary": "Reactor mission tick requires missions.write.",
            "mode": "pilot",
            "action_class": "mission_tick",
            "max_actions": 1,
        }
    )
    event_id = str(created_event["event_id"])

    dispatched = record_dispatch_attempt(
        event_id,
        {"actor": actor, "reason": "attempt mission tick without missions.write"},
    )

    assert dispatched["ok"] is True
    event = dispatched["event"]
    assert event["status"] == "dispatch_blocked"
    assert event["stable_state"] == "mission_tick_permission_denied"
    assert event["dispatch"]["engine"] == "mission_tick"
    assert event["dispatch"]["applied"] is False
    execution_receipt = event["latest_dispatch_execution_receipt"]
    assert execution_receipt["status"] == "blocked"
    assert execution_receipt["outcome"] == "mission_tick_permission_denied"
    assert execution_receipt["route"] == "mission_tick"
    assert execution_receipt["execution_started"] is False
    assert execution_receipt["dispatch_applied"] is False
    assert execution_receipt["governance"]["execution_authority"] is False
    assert execution_receipt["governance"]["approval_authority"] is False
    verification = event["latest_verification_receipt"]
    assert verification["verification_status"] == "not_run"
    assert verification["verification_outcome"] == "mission_tick_permission_denied"
    assert verification["verified"] is False
    assert verification["execution_started"] is False

    stored_mission, read_error = mission_store.read_mission(mission.mission_id)
    assert read_error is None
    assert stored_mission is not None
    assert stored_mission.status == mission_store.MissionStatus.QUEUED


def test_reactor_failed_operation_dispatch_schedules_retry_then_deadletters(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    actor = "test.reactor.dispatch"
    monkeypatch.setenv("FRANCIS_API_ACTOR_SCOPES", json.dumps({actor: ["operations.run"]}))

    created_operation = operations_runtime.create_operation(
        action="plan.create",
        reason="reactor dispatch should preserve failed operation retry routing",
        input={"goal": "prove reactor operation failure retry routing"},
        actor=actor,
    )
    assert created_operation["ok"] is True
    operation_id = str(created_operation["operation_id"])
    run_calls: list[str] = []

    def fail_operation_run(operation_id_arg: str, **_: object) -> dict[str, object]:
        run_calls.append(operation_id_arg)
        attempt = len(run_calls)
        return {
            "ok": False,
            "status": "failed",
            "operation": {
                "id": operation_id_arg,
                "status": "failed",
                "trace_id": f"trace_failed_{attempt}",
                "run_id": f"run_failed_{attempt}",
                "output": {
                    "trace_id": f"trace_failed_{attempt}",
                    "run_id": f"run_failed_{attempt}",
                },
            },
        }

    monkeypatch.setattr(reactor_dispatch.operations_runtime, "run_operation", fail_operation_run)

    created_event = enqueue_event(
        {
            "trigger_source": "mission_queue",
            "summary": "Reactor retries a failed linked operation before deadletter.",
            "mode": "pilot",
            "action_class": "operation_run",
            "operation_id": operation_id,
            "max_actions": 2,
            "max_retries": 1,
            "backoff_seconds": 0,
        }
    )
    event_id = str(created_event["event_id"])

    first_attempt = record_dispatch_attempt(
        event_id,
        {"actor": actor, "reason": "run linked operation and preserve failure retry route"},
    )

    assert first_attempt["ok"] is True
    event = first_attempt["event"]
    assert event["status"] == "dispatch_failed"
    assert event["stable_state"] == "awaiting_retry"
    assert event["dispatch"]["engine"] == "operation_run"
    assert event["dispatch"]["applied"] is True
    assert event["dispatch"]["execution_started"] is True
    assert run_calls == [operation_id]
    execution = event["latest_dispatch_execution_receipt"]
    assert execution["status"] == "failed"
    assert execution["outcome"] == "operation_failed"
    assert execution["operation_id"] == operation_id
    assert execution["execution_started"] is True
    assert execution["dispatch_applied"] is True
    assert execution["verified"] is False
    assert execution["completion_claim_allowed"] is False
    retry_candidate = event["latest_retry_candidate"]
    assert retry_candidate["gate"] == "operation_run_failed"
    assert retry_candidate["outcome"] == "operation_failed"
    assert retry_candidate["stable_state"] == "awaiting_retry"
    assert retry_candidate["execution_started"] is True
    assert retry_candidate["retry_scheduled"] is True
    retry_schedule = event["latest_retry_schedule"]
    retry_schedule_id = str(retry_schedule["retry_schedule_id"])
    assert retry_schedule["status"] == "scheduled"
    assert retry_schedule["gate"] == "operation_run_failed"
    assert retry_schedule["stable_state"] == "awaiting_retry"
    verification = event["latest_verification_receipt"]
    assert verification["verification_status"] == "failed"
    assert verification["verification_outcome"] == "operation_failed"
    assert verification["route"] == "retry_backoff"
    assert verification["source_receipt_kind"] == "reactor.retry.schedule.receipt"
    assert verification["operation_id"] == operation_id
    assert verification["execution_started"] is True
    assert verification["dispatch_applied"] is True
    assert verification["completion_claim_allowed"] is False
    stable_return = event["latest_stable_return"]
    assert stable_return["route"] == "retry_backoff"
    assert stable_return["stable_state"] == "awaiting_retry"
    assert stable_return["source_receipt_kind"] == "reactor.retry.schedule.receipt"
    assert stable_return["operation_id"] == operation_id
    assert stable_return["execution_started"] is True
    assert stable_return["dispatch_applied"] is True
    assert stable_return["retry_scheduled"] is True
    assert reactor_review_queue(route="retry_backoff")["items"][0]["review"]["gate"] == "operation_run_failed"

    due = record_retry_due(retry_schedule_id, {"actor": actor, "reason": "make failed operation retry due"})
    assert due["status"] == "retry_due"

    retry_attempt = record_retry_dispatch_attempt(
        retry_schedule_id,
        {
            "actor": actor,
            "reason": "retry failed linked operation and exhaust retry budget",
        },
    )

    assert retry_attempt["ok"] is True
    assert retry_attempt["status"] == "retry_dispatch_attempted"
    event = retry_attempt["event"]
    assert event["status"] == "dispatch_failed"
    assert event["stable_state"] == "retry_budget_exhausted"
    assert run_calls == [operation_id, operation_id]
    retry_exhausted = event["latest_retry_exhausted"]
    assert retry_exhausted["kind"] == "reactor.retry_exhausted.receipt"
    assert retry_exhausted["outcome"] == "operation_failed"
    assert retry_exhausted["execution_started"] is True
    assert retry_exhausted["attempt_count"] == 2
    assert retry_exhausted["deadletter_enqueued"] is True
    deadletter_item = event["latest_deadletter_item"]
    assert deadletter_item["source_receipt_kind"] == "reactor.retry_exhausted.receipt"
    assert deadletter_item["gate"] == "retry_budget_exhausted"
    assert deadletter_item["status"] == "queued"
    deadletter_enqueue = event["latest_deadletter_enqueue"]
    assert deadletter_enqueue["source_receipt_kind"] == "reactor.retry_exhausted.receipt"
    assert event["latest_stable_return"]["route"] == "deadletter_queue"
    assert event["latest_stable_return"]["deadletter_enqueued"] is True
    assert event["latest_stable_return"]["retry_exhausted"] is True
    assert event["latest_verification_receipt"]["verification_status"] == "failed"
    assert event["latest_verification_receipt"]["route"] == "deadletter_queue"
    assert event["latest_verification_receipt"]["completion_claim_allowed"] is False
    assert get_deadletter(str(deadletter_item["deadletter_id"]))["event_id"] == event_id  # type: ignore[index]
    status = reactor_status()
    assert status["status_counts"] == {"dispatch_failed": 1}
    assert status["stable_state_counts"] == {"retry_budget_exhausted": 1}
    assert status["dispatch_execution_counts"] == {"failed": 1}
    assert status["retry_schedule_counts"] == {"attempted": 1}
    assert status["retry_exhausted_counts"] == {"exhausted": 1}
    assert status["deadletter_queue_counts"] == {"queued": 1}


def test_reactor_due_retry_dispatch_can_return_to_successful_stable_state(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    actor = "test.reactor.dispatch"
    monkeypatch.setenv("FRANCIS_API_ACTOR_SCOPES", json.dumps({actor: ["operations.run"]}))

    created_operation = operations_runtime.create_operation(
        action="plan.create",
        reason="reactor dispatch should preserve successful due retry readback",
        input={"goal": "prove reactor operation retry success routing"},
        actor=actor,
    )
    assert created_operation["ok"] is True
    operation_id = str(created_operation["operation_id"])
    run_calls: list[str] = []

    def fail_then_succeed_operation_run(operation_id_arg: str, **_: object) -> dict[str, object]:
        run_calls.append(operation_id_arg)
        attempt = len(run_calls)
        if attempt == 1:
            return {
                "ok": False,
                "status": "failed",
                "operation": {
                    "id": operation_id_arg,
                    "status": "failed",
                    "trace_id": "trace_retry_failed",
                    "run_id": "run_retry_failed",
                    "output": {
                        "trace_id": "trace_retry_failed",
                        "run_id": "run_retry_failed",
                    },
                },
            }
        return {
            "ok": True,
            "status": "succeeded",
            "operation": {
                "id": operation_id_arg,
                "status": "succeeded",
                "trace_id": "trace_retry_succeeded",
                "run_id": "run_retry_succeeded",
                "output": {
                    "trace_id": "trace_retry_succeeded",
                    "run_id": "run_retry_succeeded",
                },
            },
        }

    monkeypatch.setattr(reactor_dispatch.operations_runtime, "run_operation", fail_then_succeed_operation_run)

    created_event = enqueue_event(
        {
            "trigger_source": "mission_queue",
            "summary": "Reactor can settle after a successful due retry.",
            "mode": "pilot",
            "action_class": "operation_run",
            "operation_id": operation_id,
            "max_actions": 2,
            "max_retries": 1,
            "backoff_seconds": 0,
        }
    )
    event_id = str(created_event["event_id"])

    first_attempt = record_dispatch_attempt(
        event_id,
        {"actor": actor, "reason": "run linked operation and schedule retry after failure"},
    )
    assert first_attempt["event"]["status"] == "dispatch_failed"
    assert first_attempt["event"]["stable_state"] == "awaiting_retry"
    retry_schedule_id = str(first_attempt["event"]["latest_retry_schedule"]["retry_schedule_id"])

    due = record_retry_due(retry_schedule_id, {"actor": actor, "reason": "make operation retry due"})
    assert due["status"] == "retry_due"

    retry_attempt = record_retry_dispatch_attempt(
        retry_schedule_id,
        {
            "actor": actor,
            "reason": "retry linked operation and settle on success",
        },
    )

    assert retry_attempt["ok"] is True
    assert retry_attempt["status"] == "retry_dispatch_attempted"
    event = retry_attempt["event"]
    assert event["status"] == "dispatch_completed"
    assert event["stable_state"] == "dispatch_succeeded"
    assert run_calls == [operation_id, operation_id]
    retry_dispatch_receipt = event["latest_retry_dispatch_attempt_receipt"]
    assert retry_dispatch_receipt["kind"] == "reactor.retry.dispatch_attempt.receipt"
    assert retry_dispatch_receipt["retry_schedule_id"] == retry_schedule_id
    assert retry_dispatch_receipt["status"] == "attempted"
    assert retry_dispatch_receipt["execution_started"] is False
    assert retry_dispatch_receipt["dispatch_applied"] is False
    execution = event["latest_dispatch_execution_receipt"]
    assert execution["status"] == "completed"
    assert execution["outcome"] == "operation_succeeded"
    assert execution["operation_id"] == operation_id
    assert execution["operation_status"] == "succeeded"
    assert execution["trace_id"] == "trace_retry_succeeded"
    assert execution["run_id"] == "run_retry_succeeded"
    assert execution["attempt_count"] == 2
    assert execution["execution_started"] is True
    assert execution["dispatch_applied"] is True
    assert execution["verified"] is True
    assert execution["completion_claim_allowed"] is True
    verification = event["latest_verification_receipt"]
    assert verification["verification_status"] == "passed"
    assert verification["verification_outcome"] == "operation_succeeded"
    assert verification["route"] == "operation_run"
    assert verification["source_receipt_kind"] == "reactor.dispatch.execution.receipt"
    assert verification["operation_id"] == operation_id
    assert verification["execution_started"] is True
    assert verification["dispatch_applied"] is True
    assert verification["completion_claim_allowed"] is True
    stable_return = event["latest_stable_return"]
    assert stable_return["route"] == "operation_run"
    assert stable_return["stable_state"] == "dispatch_succeeded"
    assert stable_return["source_receipt_kind"] == "reactor.dispatch.execution.receipt"
    assert stable_return["operation_id"] == operation_id
    assert stable_return["trace_id"] == "trace_retry_succeeded"
    assert stable_return["run_id"] == "run_retry_succeeded"
    assert stable_return["dispatch_applied"] is True
    assert stable_return["execution_started"] is True
    assert stable_return["retry_scheduled"] is False
    assert stable_return["retry_exhausted"] is False
    assert stable_return["deadletter_enqueued"] is False
    assert event["latest_retry_schedule"]["status"] == "attempted"
    assert "latest_deadletter_item" not in event
    assert reactor_review_queue(route="retry_backoff")["available_total"] == 0
    assert reactor_review_queue(route="operation_run")["available_total"] == 0
    assert {item["event_id"] for item in list_events(stable_state="dispatch_succeeded")} == {event_id}
    assert {item["event_id"] for item in list_events(receipt_kind="reactor.retry.dispatch_attempt.receipt")} == {
        event_id
    }
    status = reactor_status()
    assert status["status_counts"] == {"dispatch_completed": 1}
    assert status["stable_state_counts"] == {"dispatch_succeeded": 1}
    assert status["dispatch_execution_counts"] == {"completed": 1}
    assert status["retry_schedule_counts"] == {"attempted": 1}
    assert status["retry_dispatch_attempt_counts"] == {"attempted": 1}
    assert status["verification_counts"] == {"passed": 1}
    assert status["verification_outcome_counts"] == {"operation_succeeded": 1}
    assert status["deadletter_queue_counts"] == {}
    assert status["deadletter_total"] == 0


def test_reactor_dispatch_engine_blocks_operation_run_without_operations_scope(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    actor = "test.reactor.dispatch"
    monkeypatch.setenv("FRANCIS_API_ACTOR_SCOPES", json.dumps({actor: ["reactor.write"]}))

    created_operation = operations_runtime.create_operation(
        action="plan.create",
        reason="reactor dispatch should not bypass operations.run",
        input={"goal": "prove dispatch permission gate"},
        actor=actor,
    )
    assert created_operation["ok"] is True
    operation_id = str(created_operation["operation_id"])

    created_event = enqueue_event(
        {
            "trigger_source": "mission_queue",
            "summary": "Reactor operation dispatch needs operations.run.",
            "mode": "pilot",
            "action_class": "operation_run",
            "operation_id": operation_id,
            "max_actions": 1,
        }
    )
    event_id = str(created_event["event_id"])

    dispatched = record_dispatch_attempt(
        event_id,
        {"actor": actor, "reason": "attempt without operations.run"},
    )

    assert dispatched["ok"] is True
    event = dispatched["event"]
    assert event["status"] == "dispatch_blocked"
    assert event["stable_state"] == "operation_run_permission_denied"
    assert event["dispatch"]["applied"] is False
    assert event["dispatch"]["engine"] == "operation_run"
    execution_receipt = event["latest_dispatch_execution_receipt"]
    assert execution_receipt["status"] == "blocked"
    assert execution_receipt["outcome"] == "operation_run_permission_denied"
    assert execution_receipt["execution_started"] is False
    assert execution_receipt["dispatch_applied"] is False
    assert execution_receipt["governance"]["execution_authority"] is False
    assert execution_receipt["governance"]["approval_authority"] is False
    verification = event["latest_verification_receipt"]
    assert verification["verification_status"] == "not_run"
    assert verification["verification_outcome"] == "operation_run_permission_denied"
    assert verification["verified"] is False
    assert verification["execution_started"] is False

    operation_detail = operations_runtime.get_operation_detail(operation_id)
    assert operation_detail["operation"]["status"] == "queued"


def test_reactor_dispatch_attempt_records_retry_schedule_without_starting_retry(
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
            "action_class": "classify",
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
    assert retry_candidate["retry_scheduled"] is True
    assert retry_candidate["retry_started"] is False
    assert retry_candidate["execution_started"] is False
    assert retry_candidate["applied"] is False
    retry_schedule = event["dispatch"]["retry_schedule"]
    assert retry_schedule["kind"] == "reactor.retry_schedule.item"
    assert retry_schedule["event_id"] == event_id
    assert retry_schedule["candidate_id"] == retry_candidate["candidate_id"]
    assert retry_schedule["status"] == "scheduled"
    assert retry_schedule["route"] == "retry_backoff"
    assert retry_schedule["gate"] == "dispatch_engine_not_implemented"
    assert retry_schedule["due_after_ts"] == retry_candidate["next_retry_after_ts"]
    assert retry_schedule["retry_scheduled"] is True
    assert retry_schedule["retry_started"] is False
    assert retry_schedule["execution_started"] is False
    assert retry_schedule["dispatch_applied"] is False
    assert retry_schedule["governance"]["execution_authority"] is False
    assert retry_schedule["governance"]["dispatch_authority"] is False
    assert retry_schedule["governance"]["retry_execution_authority"] is False
    retry_schedule_receipt = event["dispatch"]["retry_schedule_receipt"]
    assert retry_schedule_receipt["kind"] == "reactor.retry.schedule.receipt"
    assert retry_schedule_receipt["retry_schedule_id"] == retry_schedule["retry_schedule_id"]
    assert retry_schedule_receipt["candidate_id"] == retry_candidate["candidate_id"]
    assert retry_schedule_receipt["status"] == "scheduled"
    assert retry_schedule_receipt["retry_scheduled"] is True
    assert retry_schedule_receipt["retry_started"] is False
    assert event["latest_retry_candidate"]["candidate_id"] == retry_candidate["candidate_id"]
    assert event["latest_retry_schedule"]["retry_schedule_id"] == retry_schedule["retry_schedule_id"]
    assert event["latest_retry_schedule_receipt"]["retry_schedule_id"] == retry_schedule["retry_schedule_id"]
    _assert_verification(
        event,
        route="retry_backoff",
        stable_state="awaiting_dispatch_engine",
        source_kind="reactor.retry.schedule.receipt",
        verification_status="not_run",
        verification_outcome="retry_scheduled",
    )
    _assert_stable_return(
        event,
        route="retry_backoff",
        stable_state="awaiting_dispatch_engine",
        source_kind="reactor.retry.schedule.receipt",
        retry_candidate=True,
    )
    assert event["latest_stable_return"]["retry_scheduled"] is True
    assert event["latest_dispatch_attempt_receipt"]["kind"] == "reactor.dispatch_attempt.receipt"
    assert event["receipts"][-5]["kind"] == "reactor.dispatch_attempt.receipt"
    assert event["receipts"][-4]["kind"] == "reactor.retry_candidate.receipt"
    assert event["receipts"][-3]["kind"] == "reactor.retry.schedule.receipt"
    assert event["receipts"][-2]["kind"] == "reactor.verification.receipt"
    assert event["receipts"][-1]["kind"] == "reactor.stable_return.receipt"
    assert event["decision_journal"][-1]["retry_candidate_id"] == retry_candidate["candidate_id"]
    assert event["decision_journal"][-1]["retry_schedule_id"] == retry_schedule["retry_schedule_id"]
    assert event["decision_journal"][-1]["retry_scheduled"] is True
    assert event["governance"]["dispatch_authority"] is False
    assert event["governance"]["execution_authority"] is False
    assert event["governance"]["retry_execution_authority"] is False

    stored = get_event(event_id)
    assert stored is not None
    assert stored["latest_retry_candidate"]["candidate_id"] == retry_candidate["candidate_id"]
    assert stored["latest_retry_schedule"]["retry_schedule_id"] == retry_schedule["retry_schedule_id"]
    assert get_retry_schedule(str(retry_schedule["retry_schedule_id"]))["event_id"] == event_id  # type: ignore[index]
    assert [item["retry_schedule_id"] for item in list_retry_schedules()] == [retry_schedule["retry_schedule_id"]]
    status = reactor_status()
    assert status["status_counts"] == {"dispatch_deferred": 1}
    assert status["retry_candidate_counts"] == {"candidate": 1}
    assert status["retry_schedule_counts"] == {"scheduled": 1}
    assert status["retry_schedule_total"] == 1
    assert status["verification_counts"] == {"not_run": 1}
    assert status["verification_outcome_counts"] == {"retry_scheduled": 1}
    assert status["stable_return_counts"] == {"settled": 1}


def test_reactor_retry_schedule_due_handoff_records_receipt_without_execution(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    created = enqueue_event(
        {
            "trigger_source": "mission_queue",
            "summary": "Mission queue item retry can become due",
            "mode": "pilot",
            "action_class": "classify",
            "max_actions": 2,
            "max_runtime_seconds": 90,
            "max_retries": 2,
            "backoff_seconds": 0,
        }
    )
    event_id = str(created["event_id"])
    attempted = record_dispatch_attempt(
        event_id,
        {
            "actor": "reactor.test",
            "reason": "schedule immediate retry handoff",
        },
    )
    retry_schedule_id = str(attempted["event"]["dispatch"]["retry_schedule"]["retry_schedule_id"])

    handed = record_retry_due(
        retry_schedule_id,
        {
            "actor": "reactor.test",
            "reason": "mark retry due without dispatching it",
        },
    )

    assert handed["ok"] is True
    assert handed["applied"] is True
    assert handed["status"] == "retry_due"
    event = handed["event"]
    assert event["status"] == "dispatch_deferred"
    assert event["stable_state"] == "retry_due"
    due_receipt = event["latest_retry_due_receipt"]
    assert due_receipt["kind"] == "reactor.retry.due.receipt"
    assert due_receipt["retry_schedule_id"] == retry_schedule_id
    assert due_receipt["status"] == "due"
    assert due_receipt["route"] == "retry_due"
    assert due_receipt["stable_state"] == "retry_due"
    assert due_receipt["next_step"] == "record_bounded_dispatch_attempt_for_due_retry"
    assert due_receipt["retry_due"] is True
    assert due_receipt["retry_started"] is False
    assert due_receipt["execution_started"] is False
    assert due_receipt["dispatch_applied"] is False
    assert due_receipt["applied"] is True
    assert due_receipt["governance"]["execution_authority"] is False
    assert due_receipt["governance"]["dispatch_authority"] is False
    assert due_receipt["governance"]["retry_execution_authority"] is False
    assert event["dispatch"]["retry_schedule"]["status"] == "due"
    assert event["dispatch"]["retry_schedule"]["retry_started"] is False
    assert event["dispatch"]["retry_due"] is True
    assert event["dispatch"]["retry_due_receipt"]["retry_schedule_id"] == retry_schedule_id
    assert event["latest_receipt"]["retry_schedule_id"] == retry_schedule_id
    assert event["decision_journal"][-1]["kind"] == "reactor.retry.due_handoff"
    assert event["decision_journal"][-1]["retry_schedule_id"] == retry_schedule_id
    assert event["decision_journal"][-1]["retry_started"] is False
    assert event["governance"]["retry_due"] is True
    assert event["governance"]["retry_execution_authority"] is False

    stored_schedule = get_retry_schedule(retry_schedule_id)
    assert stored_schedule is not None
    assert stored_schedule["status"] == "due"
    assert stored_schedule["retry_started"] is False
    assert [item["retry_schedule_id"] for item in list_retry_schedules(status="due")] == [retry_schedule_id]
    assert {item["event_id"] for item in list_events(stable_state="retry_due")} == {event_id}
    assert {item["event_id"] for item in list_events(review_route="retry_due")} == {event_id}
    assert {item["event_id"] for item in list_events(receipt_kind="reactor.retry.due.receipt")} == {event_id}

    review_queue = reactor_review_queue(route="retry_due")
    assert review_queue["available_total"] == 1
    assert review_queue["items"][0]["review"]["receipt_kind"] == "reactor.retry.due.receipt"
    assert review_queue["items"][0]["review"]["action"] == "record_dispatch_attempt_for_due_retry"
    status = reactor_status()
    assert status["stable_state_counts"] == {"retry_due": 1}
    assert status["retry_schedule_counts"] == {"due": 1}
    assert status["retry_schedule_total"] == 1
    assert status["retry_due_counts"] == {"due": 1}

    second_handoff = record_retry_due(
        retry_schedule_id,
        {
            "actor": "reactor.test",
            "reason": "mark retry due again",
        },
    )

    assert second_handoff["ok"] is True
    assert second_handoff["applied"] is False
    assert second_handoff["status"] == "already_due"
    assert len(second_handoff["event"]["retry_due_receipts"]) == 1


def test_reactor_due_retry_dispatch_attempt_records_source_receipt_without_execution(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    created = enqueue_event(
        {
            "trigger_source": "mission_queue",
            "summary": "Mission queue due retry can attempt bounded dispatch",
            "mode": "pilot",
            "action_class": "classify",
            "max_actions": 2,
            "max_runtime_seconds": 90,
            "max_retries": 2,
            "backoff_seconds": 0,
        }
    )
    event_id = str(created["event_id"])
    first_attempt = record_dispatch_attempt(event_id, {"actor": "reactor.test"})
    retry_schedule_id = str(first_attempt["event"]["dispatch"]["retry_schedule"]["retry_schedule_id"])
    due = record_retry_due(retry_schedule_id, {"actor": "reactor.test"})
    assert due["status"] == "retry_due"

    retry_attempt = record_retry_dispatch_attempt(
        retry_schedule_id,
        {
            "actor": "reactor.test",
            "reason": "record bounded dispatch attempt for due retry",
        },
    )

    assert retry_attempt["ok"] is True
    assert retry_attempt["applied"] is True
    assert retry_attempt["status"] == "retry_dispatch_attempted"
    event = retry_attempt["event"]
    assert event["status"] == "dispatch_deferred"
    assert event["stable_state"] == "awaiting_dispatch_engine"
    retry_dispatch_receipt = event["latest_retry_dispatch_attempt_receipt"]
    assert retry_dispatch_receipt["kind"] == "reactor.retry.dispatch_attempt.receipt"
    assert retry_dispatch_receipt["retry_schedule_id"] == retry_schedule_id
    assert retry_dispatch_receipt["status"] == "attempted"
    assert retry_dispatch_receipt["route"] == "dispatch_engine"
    assert retry_dispatch_receipt["retry_dispatch_attempted"] is True
    assert retry_dispatch_receipt["retry_started"] is False
    assert retry_dispatch_receipt["execution_started"] is False
    assert retry_dispatch_receipt["dispatch_applied"] is False
    assert retry_dispatch_receipt["governance"]["execution_authority"] is False
    assert retry_dispatch_receipt["governance"]["dispatch_authority"] is False
    assert retry_dispatch_receipt["governance"]["retry_execution_authority"] is False
    assert event["dispatch"]["retry_dispatch_attempted"] is True
    assert event["dispatch"]["retry_dispatch_source_schedule_id"] == retry_schedule_id
    assert event["dispatch"]["retry_attempted_schedule"]["status"] == "attempted"
    assert event["dispatch"]["retry_attempted_schedule"]["retry_started"] is False
    assert event["decision_journal"][-1]["retry_dispatch_attempted"] is True
    assert event["decision_journal"][-1]["retry_dispatch_source_schedule_id"] == retry_schedule_id
    assert event["governance"]["retry_dispatch_attempted"] is True
    assert event["governance"]["retry_execution_authority"] is False
    assert event["latest_receipt"]["kind"] == "reactor.stable_return.receipt"

    _assert_verification(
        event,
        route="retry_backoff",
        stable_state="awaiting_dispatch_engine",
        source_kind="reactor.retry.schedule.receipt",
        verification_status="not_run",
        verification_outcome="retry_scheduled",
    )
    _assert_stable_return(
        event,
        route="retry_backoff",
        stable_state="awaiting_dispatch_engine",
        source_kind="reactor.retry.schedule.receipt",
        retry_candidate=True,
    )
    assert event["latest_stable_return"]["retry_scheduled"] is True
    assert event["latest_retry_schedule"]["retry_schedule_id"] != retry_schedule_id
    assert event["latest_retry_schedule"]["status"] == "scheduled"

    stored_schedule = get_retry_schedule(retry_schedule_id)
    assert stored_schedule is not None
    assert stored_schedule["status"] == "attempted"
    assert stored_schedule["retry_dispatch_attempted"] is True
    schedules_by_status = {
        status: {item["retry_schedule_id"] for item in list_retry_schedules(status=status)}
        for status in ("attempted", "scheduled")
    }
    assert schedules_by_status["attempted"] == {retry_schedule_id}
    assert event["latest_retry_schedule"]["retry_schedule_id"] in schedules_by_status["scheduled"]
    assert {item["event_id"] for item in list_events(receipt_kind="reactor.retry.dispatch_attempt.receipt")} == {
        event_id
    }
    assert {item["event_id"] for item in list_events(review_route="retry_backoff")} == {event_id}
    assert reactor_review_queue(route="retry_due")["available_total"] == 0
    retry_review = reactor_review_queue(route="retry_backoff")
    assert retry_review["available_total"] == 1
    assert retry_review["items"][0]["review"]["receipt_kind"] == "reactor.retry.schedule.receipt"
    status = reactor_status()
    assert status["stable_state_counts"] == {"awaiting_dispatch_engine": 1}
    assert status["retry_schedule_counts"] == {"attempted": 1, "scheduled": 1}
    assert status["retry_due_counts"] == {"due": 1}
    assert status["retry_dispatch_attempt_counts"] == {"attempted": 1}
    assert status["verification_outcome_counts"] == {"retry_scheduled": 1}

    second_retry_attempt = record_retry_dispatch_attempt(
        retry_schedule_id,
        {
            "actor": "reactor.test",
            "reason": "do not duplicate due retry dispatch attempt",
        },
    )

    assert second_retry_attempt["ok"] is True
    assert second_retry_attempt["applied"] is False
    assert second_retry_attempt["status"] == "already_attempted"
    assert len(second_retry_attempt["event"]["retry_dispatch_attempt_receipts"]) == 1


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
            "action_class": "classify",
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
            "action_class": "classify",
            "max_actions": 0,
        }
    )
    budget_id = str(budget_event["event_id"])
    record_dispatch_attempt(budget_id, {"actor": "reactor.test"})

    retry_event = enqueue_event(
        {
            "trigger_source": "mission_queue",
            "summary": "Retry-exhausted event needs review",
            "action_class": "classify",
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
    assert {item["event_id"] for item in list_events(receipt_kind="reactor.retry.schedule.receipt")} == {retry_id}
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
            "action_class": "classify",
            "max_actions": 0,
        }
    )
    budget_id = str(budget_event["event_id"])
    record_dispatch_attempt(budget_id, {"actor": "reactor.test"})

    retry_event = enqueue_event(
        {
            "trigger_source": "mission_queue",
            "summary": "Retry candidate needs scheduler review",
            "action_class": "classify",
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
            "action_class": "classify",
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
    assert by_id[retry_id]["review"]["receipt_kind"] == "reactor.retry.schedule.receipt"
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
    assert event["status"] == "dispatch_blocked"
    assert event["stable_state"] == "mutate_dispatch_not_enabled"
    assert event["dispatch"]["allowed"] is False
    assert event["dispatch"]["applied"] is False
    assert event["dispatch"]["engine"] == "mutate"
    assert event["dispatch"]["execution_started"] is False
    assert event["dispatch"]["blocked_route"] == "operator_review"
    assert event["dispatch"]["blocker"]["gate"] == "mutate_dispatch_not_enabled"
    assert event["dispatch"]["blocker"]["dispatch_execution_receipt_id"]

    execution = event["latest_dispatch_execution_receipt"]
    assert execution["kind"] == "reactor.dispatch.execution.receipt"
    assert execution["status"] == "blocked"
    assert execution["route"] == "mutate"
    assert execution["gate"] == "reactor_mutate_boundary"
    assert execution["outcome"] == "mutate_dispatch_not_enabled"
    assert execution["execution_started"] is False
    assert execution["dispatch_applied"] is False
    assert execution["governance"]["mutate_authority"] is False

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
        route="operator_review",
        stable_state="mutate_dispatch_not_enabled",
        source_kind="reactor.approval_decision.receipt",
        verification_status="not_run",
        verification_outcome="mutate_dispatch_not_enabled",
    )
    _assert_stable_return(
        event,
        route="operator_review",
        stable_state="mutate_dispatch_not_enabled",
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
    assert status["status_counts"] == {"dispatch_blocked": 1}
    assert status["blocker_route_counts"] == {"operator_review": 1}
    assert status["approval_decision_counts"] == {"approved": 1}
    assert reactor_review_queue(route="approval_queue")["available_total"] == 0
    operator_review = reactor_review_queue(route="operator_review")
    assert operator_review["available_total"] == 1
    assert operator_review["items"][0]["review"]["gate"] == "mutate_dispatch_not_enabled"


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
            "action_class": "classify",
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


def test_reactor_deadletter_review_records_receipt_without_resolution(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    created = enqueue_event(
        {
            "trigger_source": "mission_queue",
            "summary": "Mission queue deadletter can be reviewed",
            "action_class": "classify",
            "max_actions": 0,
            "max_retries": 1,
            "backoff_seconds": 15,
        }
    )
    attempted = record_dispatch_attempt(str(created["event_id"]), {"actor": "reactor.test"})
    deadletter_id = str(attempted["event"]["dispatch"]["deadletter_item"]["deadletter_id"])

    reviewed = record_deadletter_review(
        deadletter_id,
        {
            "actor": "reactor.test",
            "decision": "retry_later",
            "reason": "operator reviewed failed Reactor item",
        },
    )

    assert reviewed["ok"] is True
    assert reviewed["applied"] is True
    assert reviewed["status"] == "deadletter_reviewed"
    event = reviewed["event"]
    assert event["stable_state"] == "deadletter_reviewed"
    assert event["dispatch"]["deadletter_reviewed"] is True
    assert event["dispatch"]["deadletter_review_decision"] == "retry_later"
    review_receipt = event["latest_deadletter_review_receipt"]
    assert review_receipt["kind"] == "reactor.deadletter.review.receipt"
    assert review_receipt["deadletter_id"] == deadletter_id
    assert review_receipt["status"] == "reviewed"
    assert review_receipt["route"] == "deadletter_review"
    assert review_receipt["stable_state"] == "deadletter_reviewed"
    assert review_receipt["review_decision"] == "retry_later"
    assert review_receipt["deadletter_resolved"] is False
    assert review_receipt["recovery_started"] is False
    assert review_receipt["retry_started"] is False
    assert review_receipt["execution_started"] is False
    assert review_receipt["escalation_started"] is False
    assert review_receipt["governance"]["deadletter_resolution_authority"] is False
    assert review_receipt["governance"]["escalation_authority"] is False
    assert review_receipt["governance"]["retry_authority"] is False
    assert event["latest_receipt"]["kind"] == "reactor.deadletter.review.receipt"
    assert event["latest_deadletter_item"]["status"] == "reviewed"
    assert event["deadletter_reviews"][0]["deadletter_id"] == deadletter_id
    assert event["decision_journal"][-1]["kind"] == "reactor.deadletter.reviewed"
    assert event["decision_journal"][-1]["deadletter_resolved"] is False
    assert event["decision_journal"][-1]["retry_started"] is False
    assert event["decision_journal"][-1]["escalation_started"] is False
    assert event["governance"]["deadletter_reviewed"] is True
    assert event["governance"]["deadletter_resolved"] is False
    assert event["governance"]["deadletter_resolution_authority"] is False

    stored_deadletter = get_deadletter(deadletter_id)
    assert stored_deadletter is not None
    assert stored_deadletter["status"] == "reviewed"
    assert stored_deadletter["latest_review_receipt"]["review_decision"] == "retry_later"
    assert [item["deadletter_id"] for item in list_deadletters(status="reviewed")] == [deadletter_id]
    assert {item["event_id"] for item in list_events(stable_state="deadletter_reviewed")} == {str(created["event_id"])}
    assert {item["event_id"] for item in list_events(review_route="deadletter_review")} == {str(created["event_id"])}
    assert {item["event_id"] for item in list_events(receipt_kind="reactor.deadletter.review.receipt")} == {
        str(created["event_id"])
    }

    review_queue = reactor_review_queue(route="deadletter_review")
    assert review_queue["available_total"] == 1
    assert review_queue["items"][0]["review"]["receipt_kind"] == "reactor.deadletter.review.receipt"
    assert review_queue["items"][0]["review"]["action"] == "wait_for_deadletter_resolution_or_escalation_path"
    status = reactor_status()
    assert status["stable_state_counts"] == {"deadletter_reviewed": 1}
    assert status["deadletter_queue_counts"] == {"reviewed": 1}
    assert status["deadletter_review_counts"] == {"reviewed": 1}
    assert status["deadletter_total"] == 1

    second_review = record_deadletter_review(
        deadletter_id,
        {
            "actor": "reactor.test",
            "decision": "retry_later",
            "reason": "same review should not duplicate receipts",
        },
    )

    assert second_review["ok"] is True
    assert second_review["applied"] is False
    assert second_review["status"] == "already_reviewed"
    assert len(second_review["event"]["deadletter_reviews"]) == 1


def test_reactor_deadletter_resolution_records_receipt_without_recovery(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    created = enqueue_event(
        {
            "trigger_source": "mission_queue",
            "summary": "Mission queue deadletter can be dispositioned",
            "action_class": "classify",
            "max_actions": 0,
            "max_retries": 1,
            "backoff_seconds": 15,
        }
    )
    attempted = record_dispatch_attempt(str(created["event_id"]), {"actor": "reactor.test"})
    deadletter_id = str(attempted["event"]["dispatch"]["deadletter_item"]["deadletter_id"])
    direct_resolution = record_deadletter_resolution(
        deadletter_id,
        {
            "actor": "reactor.test",
            "decision": "resolved_no_action",
            "reason": "queued deadletter should require review before disposition",
        },
    )
    assert direct_resolution["ok"] is False
    assert direct_resolution["applied"] is False
    assert direct_resolution["error"] == "deadletter_review_required"

    reviewed = record_deadletter_review(
        deadletter_id,
        {
            "actor": "reactor.test",
            "decision": "operator_reviewed",
            "reason": "operator reviewed failed Reactor item",
        },
    )
    assert reviewed["status"] == "deadletter_reviewed"

    resolved = record_deadletter_resolution(
        deadletter_id,
        {
            "actor": "reactor.test",
            "decision": "resolved_no_action",
            "reason": "operator confirmed no recovery is needed",
        },
    )

    assert resolved["ok"] is True
    assert resolved["applied"] is True
    assert resolved["status"] == "deadletter_resolved"
    event = resolved["event"]
    assert event["stable_state"] == "deadletter_resolved"
    assert event["dispatch"]["deadletter_resolved"] is True
    assert event["dispatch"]["deadletter_escalation_recorded"] is False
    assert event["dispatch"]["deadletter_resolution_decision"] == "resolved_no_action"
    receipt = event["latest_deadletter_resolution_receipt"]
    assert receipt["kind"] == "reactor.deadletter.resolution.receipt"
    assert receipt["deadletter_id"] == deadletter_id
    assert receipt["status"] == "resolved"
    assert receipt["route"] == "deadletter_resolution"
    assert receipt["stable_state"] == "deadletter_resolved"
    assert receipt["resolution_decision"] == "resolved_no_action"
    assert receipt["deadletter_resolved"] is True
    assert receipt["escalation_recorded"] is False
    assert receipt["recovery_started"] is False
    assert receipt["retry_started"] is False
    assert receipt["execution_started"] is False
    assert receipt["escalation_started"] is False
    assert receipt["memory_write"] is False
    assert receipt["governance"]["deadletter_disposition_authority"] is True
    assert receipt["governance"]["deadletter_resolution_authority"] is True
    assert receipt["governance"]["escalation_authority"] is False
    assert receipt["governance"]["retry_authority"] is False
    assert event["latest_receipt"]["kind"] == "reactor.deadletter.resolution.receipt"
    assert event["latest_deadletter_item"]["status"] == "resolved"
    assert event["deadletter_resolutions"][0]["deadletter_id"] == deadletter_id
    assert event["decision_journal"][-1]["kind"] == "reactor.deadletter.resolution_recorded"
    assert event["decision_journal"][-1]["deadletter_resolved"] is True
    assert event["decision_journal"][-1]["retry_started"] is False
    assert event["decision_journal"][-1]["execution_started"] is False
    assert event["decision_journal"][-1]["escalation_started"] is False
    assert event["governance"]["deadletter_disposition_authority"] is True
    assert event["governance"]["deadletter_resolved"] is True
    assert event["governance"]["deadletter_resolution_authority"] is True
    assert event["governance"]["execution_authority"] is False
    assert event["governance"]["escalation_authority"] is False

    stored_deadletter = get_deadletter(deadletter_id)
    assert stored_deadletter is not None
    assert stored_deadletter["status"] == "resolved"
    assert stored_deadletter["latest_resolution_receipt"]["resolution_decision"] == "resolved_no_action"
    history = get_deadletter_history(deadletter_id)
    assert history is not None
    assert history["deadletter_id"] == deadletter_id
    assert history["status"] == "resolved"
    history_kinds = [entry["receipt_kind"] for entry in history["history"]]
    assert "reactor.deadletter.item" in history_kinds
    assert "reactor.deadletter.review.receipt" in history_kinds
    assert "reactor.deadletter.resolution.receipt" in history_kinds
    assert history["latest_receipt_kind"] == "reactor.deadletter.resolution.receipt"
    assert history["governance"]["deadletter_resolution_authority"] is False
    assert history["governance"]["execution_authority"] is False
    resolution_history = get_deadletter_history(
        deadletter_id,
        receipt_kind="reactor.deadletter.resolution.receipt",
    )
    assert resolution_history is not None
    assert resolution_history["total"] == 1
    assert resolution_history["history"][0]["route"] == "deadletter_resolution"
    assert get_deadletter_history("rdl_missing") is None
    assert [item["deadletter_id"] for item in list_deadletters(status="resolved")] == [deadletter_id]
    assert {item["event_id"] for item in list_events(stable_state="deadletter_resolved")} == {str(created["event_id"])}
    assert {item["event_id"] for item in list_events(review_route="deadletter_resolution")} == {
        str(created["event_id"])
    }
    assert {item["event_id"] for item in list_events(receipt_kind="reactor.deadletter.resolution.receipt")} == {
        str(created["event_id"])
    }

    review_queue = reactor_review_queue(route="deadletter_review")
    assert review_queue["available_total"] == 0
    status = reactor_status()
    assert status["stable_state_counts"] == {"deadletter_resolved": 1}
    assert status["deadletter_queue_counts"] == {"resolved": 1}
    assert status["deadletter_review_counts"] == {"reviewed": 1}
    assert status["deadletter_resolution_counts"] == {"resolved": 1}
    assert status["deadletter_total"] == 1

    second_resolution = record_deadletter_resolution(
        deadletter_id,
        {
            "actor": "reactor.test",
            "decision": "resolved_no_action",
            "reason": "same resolution should not duplicate receipts",
        },
    )

    assert second_resolution["ok"] is True
    assert second_resolution["applied"] is False
    assert second_resolution["status"] == "already_resolved"
    assert len(second_resolution["event"]["deadletter_resolutions"]) == 1


def test_reactor_external_escalation_attempt_records_adapter_preflight_without_delivery(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    created = enqueue_event(
        {
            "trigger_source": "mission_queue",
            "summary": "Escalated Reactor deadletter needs adapter preflight",
            "action_class": "classify",
            "max_actions": 0,
            "max_retries": 1,
            "backoff_seconds": 15,
        }
    )
    attempted = record_dispatch_attempt(str(created["event_id"]), {"actor": "reactor.test"})
    deadletter_id = str(attempted["event"]["dispatch"]["deadletter_item"]["deadletter_id"])
    record_deadletter_review(
        deadletter_id,
        {
            "actor": "reactor.test",
            "decision": "escalate_later",
            "reason": "operator reviewed failed Reactor item",
        },
    )
    record_deadletter_resolution(
        deadletter_id,
        {
            "actor": "reactor.test",
            "decision": "escalate",
            "reason": "operator wants escalation tracked before external preflight",
        },
    )
    record_deadletter_escalation_handoff(
        deadletter_id,
        {
            "actor": "reactor.test",
            "reason": "record external handoff before adapter preflight",
        },
    )
    record_deadletter_escalation_acknowledgement(
        deadletter_id,
        {
            "actor": "reactor.test",
            "reason": "operator acknowledged the escalation handoff",
        },
    )

    external_attempt = record_deadletter_external_escalation_attempt(
        deadletter_id,
        {
            "actor": "reactor.test",
            "reason": "preflight local outbox without sending externally",
            "external_channel": "ops_bridge",
            "external_target": "on_call",
            "external_adapter": "local-outbox",
        },
    )

    assert external_attempt["ok"] is True
    assert external_attempt["applied"] is True
    receipt = external_attempt["receipt"]
    assert receipt["external_adapter"] == "local_outbox"
    assert receipt["external_adapter_status"] == "configured"
    assert receipt["external_adapter_known"] is True
    assert receipt["external_adapter_configured"] is True
    assert receipt["external_delivery_mode"] == "local_outbox"
    assert receipt["external_delivery_ready"] is True
    assert receipt["external_delivery_queued"] is False
    assert receipt["external_delivery_started"] is False
    assert receipt["external_escalation_started"] is False
    assert receipt["execution_started"] is False
    assert receipt["memory_write"] is False
    assert receipt["next_step"] == "queue_local_outbox_external_escalation_delivery"
    assert receipt["governance"]["external_escalation_authority"] is False

    event = external_attempt["event"]
    assert event["dispatch"]["external_adapter"] == "local_outbox"
    assert event["dispatch"]["external_adapter_configured"] is True
    assert event["dispatch"]["external_delivery_ready"] is True
    assert event["dispatch"]["external_delivery_queued"] is False
    assert event["dispatch"]["external_delivery_started"] is False
    assert event["decision_journal"][-1]["external_adapter_configured"] is True
    assert event["decision_journal"][-1]["external_delivery_ready"] is True
    assert event["governance"]["external_delivery_authority"] is False

    delivery = record_deadletter_external_escalation_delivery(
        deadletter_id,
        {
            "actor": "reactor.test",
            "reason": "queue local outbox delivery without external send authority",
        },
    )

    assert delivery["ok"] is True
    assert delivery["applied"] is True
    assert delivery["status"] == "deadletter_external_escalation_delivery_queued"
    delivery_receipt = delivery["receipt"]
    delivery_id = delivery_receipt["delivery_id"]
    assert delivery_receipt["kind"] == "reactor.deadletter.external_escalation_delivery.receipt"
    assert delivery_receipt["status"] == "delivery_queued"
    assert delivery_receipt["route"] == "deadletter_external_escalation_delivery"
    assert delivery_receipt["stable_state"] == "deadletter_external_escalation_delivery_queued"
    assert delivery_receipt["source_receipt_kind"] == "reactor.deadletter.external_escalation_attempt.receipt"
    assert delivery_receipt["external_escalation_attempt_receipt_id"] == receipt["receipt_id"]
    assert delivery_receipt["external_adapter"] == "local_outbox"
    assert delivery_receipt["external_delivery_mode"] == "local_outbox"
    assert delivery_receipt["external_delivery_ready"] is True
    assert delivery_receipt["external_delivery_queued"] is True
    assert delivery_receipt["external_delivery_started"] is False
    assert delivery_receipt["external_message_sent"] is False
    assert delivery_receipt["external_network_send"] is False
    assert delivery_receipt["external_escalation_started"] is False
    assert delivery_receipt["execution_started"] is False
    assert delivery_receipt["dispatch_applied"] is False
    assert delivery_receipt["memory_write"] is False
    assert delivery_receipt["completion_claim_allowed"] is False
    assert delivery_receipt["governance"]["external_delivery_queue_authority"] is True
    assert delivery_receipt["governance"]["external_delivery_authority"] is False
    assert delivery_receipt["governance"]["external_escalation_authority"] is False

    outbox_item = delivery["delivery_item"]
    assert outbox_item["kind"] == "reactor.deadletter.external_escalation.local_outbox.item"
    assert outbox_item["delivery_id"] == delivery_id
    assert outbox_item["status"] == "queued"
    assert outbox_item["external_delivery_queued"] is True
    assert outbox_item["external_delivery_started"] is False
    assert outbox_item["external_message_sent"] is False
    assert outbox_item["external_network_send"] is False
    assert (data_root / "reactor" / "external_escalation_outbox" / f"{delivery_id}.json").exists()
    assert get_external_escalation_delivery(delivery_id)["delivery_id"] == delivery_id  # type: ignore[index]
    assert [item["delivery_id"] for item in list_external_escalation_deliveries()] == [delivery_id]
    assert [item["delivery_id"] for item in list_external_escalation_deliveries(status="queued")] == [delivery_id]
    assert [item["delivery_id"] for item in list_external_escalation_deliveries(deadletter_id=deadletter_id)] == [
        delivery_id
    ]
    assert [item["delivery_id"] for item in list_external_escalation_deliveries(event_id=str(created["event_id"]))] == [
        delivery_id
    ]
    assert list_external_escalation_deliveries(status="sent") == []
    processor_readiness = get_external_escalation_delivery_processor_readiness(delivery_id)
    assert processor_readiness is not None
    assert processor_readiness["kind"] == "reactor.deadletter.external_escalation.delivery_processor_readiness"
    assert processor_readiness["delivery_id"] == delivery_id
    assert processor_readiness["status"] == "ready"
    assert processor_readiness["delivery_status"] == "queued"
    assert processor_readiness["delivery_processor_ready"] is True
    assert processor_readiness["delivery_processor_status"] == "ready"
    assert processor_readiness["delivery_processor_blockers"] == []
    assert processor_readiness["external_delivery_started"] is False
    assert processor_readiness["external_message_sent"] is False
    assert processor_readiness["external_network_send"] is False
    assert processor_readiness["execution_started"] is False
    assert processor_readiness["completion_claim_allowed"] is False
    assert processor_readiness["governance"]["external_delivery_authority"] is False
    assert processor_readiness["governance"]["external_escalation_authority"] is False
    assert processor_readiness["governance"]["delivery_processor_claim_authority"] is False
    assert [item["delivery_id"] for item in list_external_escalation_delivery_processor_readiness()] == [delivery_id]
    assert [
        item["delivery_id"] for item in list_external_escalation_delivery_processor_readiness(processor_status="ready")
    ] == [delivery_id]
    assert list_external_escalation_delivery_processor_readiness(processor_status="blocked") == []
    assert get_external_escalation_delivery_processor_readiness("red_missing") is None

    delivered_event = delivery["event"]
    assert delivered_event["stable_state"] == "deadletter_external_escalation_delivery_queued"
    assert delivered_event["dispatch"]["deadletter_external_escalation_delivery_queued"] is True
    assert delivered_event["dispatch"]["external_delivery_id"] == delivery_id
    assert delivered_event["dispatch"]["external_delivery_queued"] is True
    assert delivered_event["dispatch"]["external_delivery_started"] is False
    assert delivered_event["dispatch"]["external_message_sent"] is False
    assert delivered_event["dispatch"]["execution_started"] is False
    assert delivered_event["latest_receipt"]["kind"] == "reactor.deadletter.external_escalation_delivery.receipt"
    assert delivered_event["latest_deadletter_item"]["status"] == "external_escalation_delivery_queued"
    assert delivered_event["deadletter_external_escalation_deliveries"][0]["delivery_id"] == delivery_id
    assert delivered_event["decision_journal"][-1]["kind"] == ("reactor.deadletter.external_escalation_delivery_queued")
    assert delivered_event["decision_journal"][-1]["external_delivery_started"] is False
    assert delivered_event["decision_journal"][-1]["external_network_send"] is False
    assert delivered_event["decision_journal"][-1]["dispatch_applied"] is False
    assert delivered_event["governance"]["external_delivery_queue_authority"] is True
    assert delivered_event["governance"]["external_delivery_authority"] is False
    assert delivered_event["governance"]["external_escalation_authority"] is False

    delivered_deadletter = get_deadletter(deadletter_id)
    assert delivered_deadletter is not None
    assert delivered_deadletter["status"] == "external_escalation_delivery_queued"
    assert delivered_deadletter["latest_external_escalation_delivery_receipt"]["delivery_id"] == delivery_id
    assert [item["deadletter_id"] for item in list_deadletters(status="external_escalation_delivery_queued")] == [
        deadletter_id
    ]
    assert {
        item["event_id"] for item in list_events(stable_state="deadletter_external_escalation_delivery_queued")
    } == {str(created["event_id"])}
    assert {item["event_id"] for item in list_events(review_route="deadletter_external_escalation_delivery")} == {
        str(created["event_id"])
    }
    assert {
        item["event_id"] for item in list_events(receipt_kind="reactor.deadletter.external_escalation_delivery.receipt")
    } == {str(created["event_id"])}

    delivery_review_queue = reactor_review_queue(route="deadletter_external_escalation_delivery")
    assert delivery_review_queue["available_total"] == 1
    assert (
        delivery_review_queue["items"][0]["review"]["action"]
        == "await_local_outbox_external_delivery_processor_or_operator_review"
    )
    delivery_status = reactor_status()
    assert delivery_status["stable_state_counts"] == {"deadletter_external_escalation_delivery_queued": 1}
    assert delivery_status["deadletter_queue_counts"] == {"external_escalation_delivery_queued": 1}
    assert delivery_status["deadletter_external_escalation_attempt_counts"] == {"attempt_recorded": 1}
    assert delivery_status["deadletter_external_escalation_delivery_counts"] == {"delivery_queued": 1}

    second_delivery = record_deadletter_external_escalation_delivery(
        deadletter_id,
        {
            "actor": "reactor.test",
            "reason": "same local outbox delivery should not duplicate receipts",
        },
    )
    assert second_delivery["ok"] is True
    assert second_delivery["applied"] is False
    assert second_delivery["status"] == "already_external_escalation_delivery_queued"
    assert len(second_delivery["event"]["deadletter_external_escalation_deliveries"]) == 1

    handoff = record_deadletter_external_escalation_delivery_processor_handoff(
        delivery_id,
        {
            "actor": "reactor.test",
            "reason": "record processor handoff without claiming external send",
        },
    )

    assert handoff["ok"] is True
    assert handoff["applied"] is True
    assert handoff["status"] == "deadletter_external_escalation_delivery_processor_handoff_recorded"
    handoff_receipt = handoff["receipt"]
    assert handoff_receipt["kind"] == "reactor.deadletter.external_escalation_delivery_processor_handoff.receipt"
    assert handoff_receipt["status"] == "processor_handoff_recorded"
    assert handoff_receipt["route"] == "deadletter_external_escalation_delivery_processor_handoff"
    assert handoff_receipt["stable_state"] == "deadletter_external_escalation_delivery_processor_handoff_recorded"
    assert handoff_receipt["source_receipt_kind"] == "reactor.deadletter.external_escalation_delivery.receipt"
    assert handoff_receipt["external_adapter"] == "local_outbox"
    assert handoff_receipt["external_delivery_queued"] is True
    assert handoff_receipt["external_delivery_started"] is False
    assert handoff_receipt["external_message_sent"] is False
    assert handoff_receipt["external_network_send"] is False
    assert handoff_receipt["external_escalation_started"] is False
    assert handoff_receipt["delivery_processor_handoff_recorded"] is True
    assert handoff_receipt["delivery_processor_completed"] is False
    assert handoff_receipt["execution_started"] is False
    assert handoff_receipt["dispatch_applied"] is False
    assert handoff_receipt["memory_write"] is False
    assert handoff_receipt["completion_claim_allowed"] is False
    assert handoff_receipt["governance"]["delivery_processor_handoff_authority"] is True
    assert handoff_receipt["governance"]["external_delivery_authority"] is False
    assert handoff_receipt["governance"]["external_escalation_authority"] is False

    handoff_outbox_item = handoff["delivery_item"]
    assert handoff_outbox_item["delivery_id"] == delivery_id
    assert handoff_outbox_item["status"] == "processor_handoff_recorded"
    assert handoff_outbox_item["delivery_processor_handoff_recorded"] is True
    assert handoff_outbox_item["delivery_processor_completed"] is False
    assert handoff_outbox_item["external_delivery_started"] is False
    assert handoff_outbox_item["external_message_sent"] is False
    assert handoff_outbox_item["external_network_send"] is False
    assert get_external_escalation_delivery(delivery_id)["status"] == "processor_handoff_recorded"  # type: ignore[index]
    post_handoff_readiness = get_external_escalation_delivery_processor_readiness(delivery_id)
    assert post_handoff_readiness is not None
    assert post_handoff_readiness["delivery_processor_status"] == "blocked"
    assert post_handoff_readiness["delivery_processor_blockers"] == ["delivery_not_queued"]

    handoff_event = handoff["event"]
    assert handoff_event["stable_state"] == "deadletter_external_escalation_delivery_processor_handoff_recorded"
    assert handoff_event["dispatch"]["deadletter_external_escalation_delivery_processor_handoff_recorded"] is True
    assert handoff_event["dispatch"]["delivery_processor_handoff_recorded"] is True
    assert handoff_event["dispatch"]["delivery_processor_completed"] is False
    assert handoff_event["dispatch"]["external_delivery_started"] is False
    assert handoff_event["dispatch"]["external_network_send"] is False
    assert handoff_event["latest_receipt"]["kind"] == (
        "reactor.deadletter.external_escalation_delivery_processor_handoff.receipt"
    )
    assert handoff_event["decision_journal"][-1]["kind"] == (
        "reactor.deadletter.external_escalation_delivery_processor_handoff_recorded"
    )
    assert handoff_event["governance"]["delivery_processor_handoff_authority"] is True
    assert handoff_event["governance"]["external_delivery_authority"] is False

    handoff_deadletter = get_deadletter(deadletter_id)
    assert handoff_deadletter is not None
    assert handoff_deadletter["status"] == "external_escalation_delivery_processor_handoff_recorded"
    assert [
        item["deadletter_id"]
        for item in list_deadletters(status="external_escalation_delivery_processor_handoff_recorded")
    ] == [deadletter_id]
    assert {
        item["event_id"]
        for item in list_events(stable_state="deadletter_external_escalation_delivery_processor_handoff_recorded")
    } == {str(created["event_id"])}
    assert {
        item["event_id"]
        for item in list_events(
            receipt_kind="reactor.deadletter.external_escalation_delivery_processor_handoff.receipt"
        )
    } == {str(created["event_id"])}
    assert {
        item["event_id"]
        for item in list_events(review_route="deadletter_external_escalation_delivery_processor_handoff")
    } == {str(created["event_id"])}
    handoff_history = get_deadletter_history(
        deadletter_id,
        receipt_kind="reactor.deadletter.external_escalation_delivery_processor_handoff.receipt",
    )
    assert handoff_history is not None
    assert handoff_history["total"] == 1
    assert handoff_history["history"][0]["route"] == "deadletter_external_escalation_delivery_processor_handoff"
    assert handoff_history["governance"]["external_delivery_authority"] is False

    handoff_review_queue = reactor_review_queue(route="deadletter_external_escalation_delivery_processor_handoff")
    assert handoff_review_queue["available_total"] == 1
    assert (
        handoff_review_queue["items"][0]["review"]["action"]
        == "await_explicit_external_delivery_sender_before_marking_sent"
    )
    handoff_status = reactor_status()
    assert handoff_status["stable_state_counts"] == {
        "deadletter_external_escalation_delivery_processor_handoff_recorded": 1
    }
    assert handoff_status["deadletter_queue_counts"] == {"external_escalation_delivery_processor_handoff_recorded": 1}
    assert handoff_status["deadletter_external_escalation_delivery_counts"] == {"delivery_queued": 1}
    assert handoff_status["deadletter_external_escalation_delivery_processor_handoff_counts"] == {
        "processor_handoff_recorded": 1
    }

    second_handoff = record_deadletter_external_escalation_delivery_processor_handoff(
        delivery_id,
        {
            "actor": "reactor.test",
            "reason": "processor handoff should be idempotent",
        },
    )
    assert second_handoff["ok"] is True
    assert second_handoff["applied"] is False
    assert second_handoff["status"] == "already_external_escalation_delivery_processor_handoff_recorded"

    premature_sender_attempt = record_deadletter_external_escalation_delivery_sender_attempt(
        delivery_id,
        {
            "actor": "reactor.test",
            "reason": "sender attempt must wait for processor completion",
        },
    )
    assert premature_sender_attempt["ok"] is False
    assert premature_sender_attempt["applied"] is False
    assert premature_sender_attempt["error"] == "external_escalation_delivery_processor_completion_required"

    completion = record_deadletter_external_escalation_delivery_processor_completion(
        delivery_id,
        {
            "actor": "reactor.test",
            "reason": "complete local processor without external send",
        },
    )

    assert completion["ok"] is True
    assert completion["applied"] is True
    assert completion["status"] == "deadletter_external_escalation_delivery_processor_completed"
    completion_receipt = completion["receipt"]
    assert completion_receipt["kind"] == "reactor.deadletter.external_escalation_delivery_processor_completion.receipt"
    assert completion_receipt["status"] == "processor_completed"
    assert completion_receipt["route"] == "deadletter_external_escalation_delivery_processor_completion"
    assert completion_receipt["stable_state"] == "deadletter_external_escalation_delivery_processor_completed"
    assert completion_receipt["source_receipt_kind"] == (
        "reactor.deadletter.external_escalation_delivery_processor_handoff.receipt"
    )
    assert completion_receipt["external_adapter"] == "local_outbox"
    assert completion_receipt["external_delivery_queued"] is True
    assert completion_receipt["delivery_processor_handoff_recorded"] is True
    assert completion_receipt["delivery_processor_started"] is True
    assert completion_receipt["delivery_processor_completed"] is True
    assert completion_receipt["local_outbox_processor_completed"] is True
    assert completion_receipt["external_delivery_started"] is False
    assert completion_receipt["external_message_sent"] is False
    assert completion_receipt["external_network_send"] is False
    assert completion_receipt["external_escalation_started"] is False
    assert completion_receipt["execution_started"] is False
    assert completion_receipt["dispatch_applied"] is False
    assert completion_receipt["memory_write"] is False
    assert completion_receipt["completion_claim_allowed"] is False
    assert completion_receipt["governance"]["delivery_processor_completion_authority"] is True
    assert completion_receipt["governance"]["external_delivery_authority"] is False
    assert completion_receipt["governance"]["external_escalation_authority"] is False

    processor_output = completion["processor_output"]
    assert processor_output["kind"] == "reactor.deadletter.external_escalation.local_outbox.processor_output"
    assert processor_output["status"] == "processor_completed"
    assert processor_output["delivery_id"] == delivery_id
    assert processor_output["delivery_processor_completed"] is True
    assert processor_output["external_message_sent"] is False
    assert processor_output["external_network_send"] is False
    assert (data_root / "reactor" / "external_escalation_outbox_processed" / f"{delivery_id}.json").exists()

    completed_outbox_item = completion["delivery_item"]
    assert completed_outbox_item["status"] == "processor_completed"
    assert completed_outbox_item["delivery_processor_completed"] is True
    assert completed_outbox_item["local_outbox_processor_completed"] is True
    assert completed_outbox_item["external_delivery_started"] is False
    assert completed_outbox_item["external_message_sent"] is False
    assert completed_outbox_item["external_network_send"] is False
    assert get_external_escalation_delivery(delivery_id)["status"] == "processor_completed"  # type: ignore[index]

    completion_event = completion["event"]
    assert completion_event["stable_state"] == "deadletter_external_escalation_delivery_processor_completed"
    assert completion_event["dispatch"]["deadletter_external_escalation_delivery_processor_completed"] is True
    assert completion_event["dispatch"]["delivery_processor_completed"] is True
    assert completion_event["dispatch"]["local_outbox_processor_completed"] is True
    assert completion_event["dispatch"]["external_delivery_started"] is False
    assert completion_event["dispatch"]["external_network_send"] is False
    assert completion_event["latest_receipt"]["kind"] == (
        "reactor.deadletter.external_escalation_delivery_processor_completion.receipt"
    )
    assert completion_event["decision_journal"][-1]["kind"] == (
        "reactor.deadletter.external_escalation_delivery_processor_completed"
    )
    assert completion_event["governance"]["delivery_processor_completion_authority"] is True
    assert completion_event["governance"]["external_delivery_authority"] is False

    completion_deadletter = get_deadletter(deadletter_id)
    assert completion_deadletter is not None
    assert completion_deadletter["status"] == "external_escalation_delivery_processor_completed"
    assert [
        item["deadletter_id"] for item in list_deadletters(status="external_escalation_delivery_processor_completed")
    ] == [deadletter_id]
    assert {
        item["event_id"]
        for item in list_events(stable_state="deadletter_external_escalation_delivery_processor_completed")
    } == {str(created["event_id"])}
    assert {
        item["event_id"]
        for item in list_events(
            receipt_kind="reactor.deadletter.external_escalation_delivery_processor_completion.receipt"
        )
    } == {str(created["event_id"])}
    assert {
        item["event_id"]
        for item in list_events(review_route="deadletter_external_escalation_delivery_processor_completion")
    } == {str(created["event_id"])}
    completion_history = get_deadletter_history(
        deadletter_id,
        receipt_kind="reactor.deadletter.external_escalation_delivery_processor_completion.receipt",
    )
    assert completion_history is not None
    assert completion_history["total"] == 1
    assert completion_history["history"][0]["route"] == "deadletter_external_escalation_delivery_processor_completion"

    completion_review_queue = reactor_review_queue(route="deadletter_external_escalation_delivery_processor_completion")
    assert completion_review_queue["available_total"] == 1
    assert (
        completion_review_queue["items"][0]["review"]["action"]
        == "await_explicit_external_delivery_sender_before_marking_sent"
    )
    completion_status = reactor_status()
    assert completion_status["stable_state_counts"] == {
        "deadletter_external_escalation_delivery_processor_completed": 1
    }
    assert completion_status["deadletter_queue_counts"] == {"external_escalation_delivery_processor_completed": 1}
    assert completion_status["deadletter_external_escalation_delivery_counts"] == {"delivery_queued": 1}
    assert completion_status["deadletter_external_escalation_delivery_processor_handoff_counts"] == {
        "processor_handoff_recorded": 1
    }
    assert completion_status["deadletter_external_escalation_delivery_processor_completion_counts"] == {
        "processor_completed": 1
    }

    sender_readiness = get_external_escalation_delivery_sender_readiness(delivery_id)
    assert sender_readiness is not None
    assert sender_readiness["kind"] == "reactor.deadletter.external_escalation.delivery_sender_readiness"
    assert sender_readiness["delivery_id"] == delivery_id
    assert sender_readiness["status"] == "blocked"
    assert sender_readiness["delivery_status"] == "processor_completed"
    assert sender_readiness["external_delivery_sender_ready"] is False
    assert sender_readiness["external_delivery_sender_status"] == "blocked"
    assert sender_readiness["external_delivery_sender_blockers"] == ["external_sender_adapter"]
    assert sender_readiness["external_sender_status"] == "not_configured"
    assert sender_readiness["external_sender_blocker"] == "external_sender_adapter_required"
    assert sender_readiness["delivery_processor_completed"] is True
    assert sender_readiness["local_outbox_processor_completed"] is True
    assert sender_readiness["external_delivery_started"] is False
    assert sender_readiness["external_message_sent"] is False
    assert sender_readiness["external_network_send"] is False
    assert sender_readiness["execution_started"] is False
    assert sender_readiness["completion_claim_allowed"] is False
    assert sender_readiness["governance"]["external_delivery_sender_attempt_authority"] is False
    assert sender_readiness["governance"]["external_delivery_authority"] is False
    assert sender_readiness["governance"]["external_escalation_authority"] is False
    assert [item["delivery_id"] for item in list_external_escalation_delivery_sender_readiness()] == [delivery_id]
    assert [
        item["delivery_id"] for item in list_external_escalation_delivery_sender_readiness(sender_status="blocked")
    ] == [delivery_id]
    assert list_external_escalation_delivery_sender_readiness(sender_status="ready") == []
    assert get_external_escalation_delivery_sender_readiness("red_missing") is None

    second_completion = record_deadletter_external_escalation_delivery_processor_completion(
        delivery_id,
        {
            "actor": "reactor.test",
            "reason": "processor completion should be idempotent",
        },
    )
    assert second_completion["ok"] is True
    assert second_completion["applied"] is False
    assert second_completion["status"] == "already_external_escalation_delivery_processor_completed"

    sender_attempt = record_deadletter_external_escalation_delivery_sender_attempt(
        delivery_id,
        {
            "actor": "reactor.test",
            "reason": "attempt sender boundary without configured external sender",
        },
    )

    assert sender_attempt["ok"] is True
    assert sender_attempt["applied"] is True
    assert sender_attempt["status"] == "deadletter_external_escalation_delivery_sender_blocked"
    sender_receipt = sender_attempt["receipt"]
    assert sender_receipt["kind"] == "reactor.deadletter.external_escalation_delivery_sender_attempt.receipt"
    assert sender_receipt["status"] == "sender_blocked"
    assert sender_receipt["route"] == "deadletter_external_escalation_delivery_sender_attempt"
    assert sender_receipt["stable_state"] == "deadletter_external_escalation_delivery_sender_blocked"
    assert sender_receipt["source_receipt_kind"] == (
        "reactor.deadletter.external_escalation_delivery_processor_completion.receipt"
    )
    assert sender_receipt["delivery_processor_completed"] is True
    assert sender_receipt["local_outbox_processor_completed"] is True
    assert sender_receipt["external_sender_declared"] is False
    assert sender_receipt["external_sender_ready"] is False
    assert sender_receipt["external_sender_status"] == "not_configured"
    assert sender_receipt["external_sender_blocker"] == "external_sender_adapter_required"
    assert sender_receipt["missing_requirements"] == ["external_sender_adapter"]
    assert sender_receipt["external_delivery_sender_attempted"] is True
    assert sender_receipt["external_delivery_started"] is False
    assert sender_receipt["external_message_sent"] is False
    assert sender_receipt["external_network_send"] is False
    assert sender_receipt["execution_started"] is False
    assert sender_receipt["dispatch_applied"] is False
    assert sender_receipt["memory_write"] is False
    assert sender_receipt["completion_claim_allowed"] is False
    assert sender_receipt["governance"]["external_delivery_sender_attempt_authority"] is True
    assert sender_receipt["governance"]["external_delivery_authority"] is False
    assert sender_receipt["governance"]["external_escalation_authority"] is False

    sender_delivery = sender_attempt["delivery_item"]
    assert sender_delivery["status"] == "sender_blocked"
    assert sender_delivery["external_delivery_sender_attempted"] is True
    assert sender_delivery["external_sender_ready"] is False
    assert sender_delivery["external_delivery_started"] is False
    assert sender_delivery["external_message_sent"] is False
    assert sender_delivery["external_network_send"] is False
    assert get_external_escalation_delivery(delivery_id)["status"] == "sender_blocked"  # type: ignore[index]
    assert [item["delivery_id"] for item in list_external_escalation_deliveries(status="sender_blocked")] == [
        delivery_id
    ]

    sender_event = sender_attempt["event"]
    assert sender_event["stable_state"] == "deadletter_external_escalation_delivery_sender_blocked"
    assert sender_event["dispatch"]["deadletter_external_escalation_delivery_sender_blocked"] is True
    assert sender_event["dispatch"]["external_delivery_sender_attempted"] is True
    assert sender_event["dispatch"]["external_sender_ready"] is False
    assert sender_event["dispatch"]["external_sender_blocker"] == "external_sender_adapter_required"
    assert sender_event["dispatch"]["external_delivery_started"] is False
    assert sender_event["dispatch"]["external_network_send"] is False
    assert sender_event["latest_receipt"]["kind"] == (
        "reactor.deadletter.external_escalation_delivery_sender_attempt.receipt"
    )
    assert sender_event["decision_journal"][-1]["kind"] == (
        "reactor.deadletter.external_escalation_delivery_sender_blocked"
    )
    assert sender_event["governance"]["external_delivery_sender_attempt_authority"] is True
    assert sender_event["governance"]["external_delivery_authority"] is False

    sender_deadletter = get_deadletter(deadletter_id)
    assert sender_deadletter is not None
    assert sender_deadletter["status"] == "external_escalation_delivery_sender_blocked"
    assert [
        item["deadletter_id"] for item in list_deadletters(status="external_escalation_delivery_sender_blocked")
    ] == [deadletter_id]
    assert {
        item["event_id"] for item in list_events(stable_state="deadletter_external_escalation_delivery_sender_blocked")
    } == {str(created["event_id"])}
    assert {
        item["event_id"]
        for item in list_events(receipt_kind="reactor.deadletter.external_escalation_delivery_sender_attempt.receipt")
    } == {str(created["event_id"])}
    assert {
        item["event_id"] for item in list_events(review_route="deadletter_external_escalation_delivery_sender_attempt")
    } == {str(created["event_id"])}
    sender_history = get_deadletter_history(
        deadletter_id,
        receipt_kind="reactor.deadletter.external_escalation_delivery_sender_attempt.receipt",
    )
    assert sender_history is not None
    assert sender_history["total"] == 1
    assert sender_history["history"][0]["route"] == "deadletter_external_escalation_delivery_sender_attempt"

    sender_review_queue = reactor_review_queue(route="deadletter_external_escalation_delivery_sender_attempt")
    assert sender_review_queue["available_total"] == 1
    assert (
        sender_review_queue["items"][0]["review"]["action"]
        == "configure_explicit_external_delivery_sender_before_marking_sent"
    )
    sender_status = reactor_status()
    assert sender_status["stable_state_counts"] == {"deadletter_external_escalation_delivery_sender_blocked": 1}
    assert sender_status["deadletter_queue_counts"] == {"external_escalation_delivery_sender_blocked": 1}
    assert sender_status["deadletter_external_escalation_delivery_counts"] == {"delivery_queued": 1}
    assert sender_status["deadletter_external_escalation_delivery_processor_handoff_counts"] == {
        "processor_handoff_recorded": 1
    }
    assert sender_status["deadletter_external_escalation_delivery_processor_completion_counts"] == {
        "processor_completed": 1
    }
    assert sender_status["deadletter_external_escalation_delivery_sender_attempt_counts"] == {"sender_blocked": 1}
    post_attempt_readiness = get_external_escalation_delivery_sender_readiness(delivery_id)
    assert post_attempt_readiness is not None
    assert post_attempt_readiness["delivery_status"] == "sender_blocked"
    assert post_attempt_readiness["external_delivery_sender_attempted"] is True
    assert post_attempt_readiness["external_delivery_sender_ready"] is False
    assert post_attempt_readiness["external_delivery_sender_blockers"] == ["external_sender_adapter"]
    assert post_attempt_readiness["external_delivery_started"] is False
    assert post_attempt_readiness["external_network_send"] is False

    second_sender_attempt = record_deadletter_external_escalation_delivery_sender_attempt(
        delivery_id,
        {
            "actor": "reactor.test",
            "reason": "sender boundary should be idempotent while no sender is configured",
        },
    )
    assert second_sender_attempt["ok"] is True
    assert second_sender_attempt["applied"] is False
    assert second_sender_attempt["status"] == "already_external_escalation_delivery_sender_blocked"


def test_reactor_deadletter_escalation_handoff_records_receipt_without_execution(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    operation = operations_runtime.create_operation(
        action="plan.create",
        reason="reactor deadletter recovery should target an existing operation",
        input={"goal": "prove recovery request handoff"},
        actor="reactor.test",
    )
    operation_id = str(operation["operation_id"])

    created = enqueue_event(
        {
            "trigger_source": "mission_queue",
            "summary": "Escalated Reactor deadletter needs a durable handoff",
            "action_class": "classify",
            "operation_id": operation_id,
            "max_actions": 0,
            "max_retries": 1,
            "backoff_seconds": 15,
        }
    )
    attempted = record_dispatch_attempt(str(created["event_id"]), {"actor": "reactor.test"})
    deadletter_id = str(attempted["event"]["dispatch"]["deadletter_item"]["deadletter_id"])
    reviewed = record_deadletter_review(
        deadletter_id,
        {
            "actor": "reactor.test",
            "decision": "escalate_later",
            "reason": "operator reviewed failed Reactor item",
        },
    )
    assert reviewed["status"] == "deadletter_reviewed"

    premature_handoff = record_deadletter_escalation_handoff(
        deadletter_id,
        {
            "actor": "reactor.test",
            "reason": "handoff should require escalation disposition first",
        },
    )
    assert premature_handoff["ok"] is False
    assert premature_handoff["applied"] is False
    assert premature_handoff["error"] == "deadletter_escalation_required"

    escalated = record_deadletter_resolution(
        deadletter_id,
        {
            "actor": "reactor.test",
            "decision": "escalate",
            "reason": "operator wants escalation tracked before recovery",
        },
    )
    assert escalated["status"] == "deadletter_escalation_pending"

    premature_acknowledgement = record_deadletter_escalation_acknowledgement(
        deadletter_id,
        {
            "actor": "reactor.test",
            "reason": "acknowledgement should require handoff first",
        },
    )
    assert premature_acknowledgement["ok"] is False
    assert premature_acknowledgement["applied"] is False
    assert premature_acknowledgement["error"] == "deadletter_escalation_handoff_required"

    handoff = record_deadletter_escalation_handoff(
        deadletter_id,
        {
            "actor": "reactor.test",
            "reason": "record external operator follow-up without starting execution",
        },
    )

    assert handoff["ok"] is True
    assert handoff["applied"] is True
    assert handoff["status"] == "deadletter_escalation_handoff_recorded"
    event = handoff["event"]
    assert event["stable_state"] == "deadletter_escalation_handoff_recorded"
    assert event["dispatch"]["deadletter_escalation_handoff_recorded"] is True
    receipt = event["latest_deadletter_escalation_handoff_receipt"]
    assert receipt["kind"] == "reactor.deadletter.escalation_handoff.receipt"
    assert receipt["deadletter_id"] == deadletter_id
    assert receipt["status"] == "handoff_recorded"
    assert receipt["route"] == "deadletter_escalation_handoff"
    assert receipt["stable_state"] == "deadletter_escalation_handoff_recorded"
    assert receipt["resolution_decision"] == "escalation_pending"
    assert receipt["escalation_handoff_recorded"] is True
    assert receipt["external_escalation_started"] is False
    assert receipt["recovery_started"] is False
    assert receipt["retry_started"] is False
    assert receipt["execution_started"] is False
    assert receipt["escalation_started"] is False
    assert receipt["memory_write"] is False
    assert receipt["governance"]["execution_authority"] is False
    assert receipt["governance"]["retry_authority"] is False
    assert receipt["governance"]["escalation_authority"] is False
    assert receipt["governance"]["memory_write"] is False
    assert event["latest_receipt"]["kind"] == "reactor.deadletter.escalation_handoff.receipt"
    assert event["latest_deadletter_item"]["status"] == "escalation_handoff_recorded"
    assert event["deadletter_escalation_handoffs"][0]["deadletter_id"] == deadletter_id
    assert event["decision_journal"][-1]["kind"] == "reactor.deadletter.escalation_handoff_recorded"
    assert event["decision_journal"][-1]["applied"] is True
    assert event["decision_journal"][-1]["execution_started"] is False
    assert event["decision_journal"][-1]["escalation_started"] is False
    assert event["governance"]["deadletter_escalation_handoff_recorded"] is True
    assert event["governance"]["execution_authority"] is False
    assert event["governance"]["escalation_authority"] is False

    stored_deadletter = get_deadletter(deadletter_id)
    assert stored_deadletter is not None
    assert stored_deadletter["status"] == "escalation_handoff_recorded"
    assert stored_deadletter["latest_escalation_handoff_receipt"]["deadletter_id"] == deadletter_id
    assert [item["deadletter_id"] for item in list_deadletters(status="escalation_handoff_recorded")] == [deadletter_id]
    assert {item["event_id"] for item in list_events(stable_state="deadletter_escalation_handoff_recorded")} == {
        str(created["event_id"])
    }
    assert {item["event_id"] for item in list_events(review_route="deadletter_escalation_handoff")} == {
        str(created["event_id"])
    }
    assert {item["event_id"] for item in list_events(receipt_kind="reactor.deadletter.escalation_handoff.receipt")} == {
        str(created["event_id"])
    }

    review_queue = reactor_review_queue(route="deadletter_escalation_handoff")
    assert review_queue["available_total"] == 1
    assert review_queue["items"][0]["review"]["action"] == "track_escalation_handoff_until_acknowledged"
    status = reactor_status()
    assert status["stable_state_counts"] == {"deadletter_escalation_handoff_recorded": 1}
    assert status["deadletter_queue_counts"] == {"escalation_handoff_recorded": 1}
    assert status["deadletter_review_counts"] == {"reviewed": 1}
    assert status["deadletter_resolution_counts"] == {"escalation_pending": 1}
    assert status["deadletter_escalation_handoff_counts"] == {"handoff_recorded": 1}

    second_handoff = record_deadletter_escalation_handoff(
        deadletter_id,
        {
            "actor": "reactor.test",
            "reason": "same handoff should not duplicate receipts",
        },
    )

    assert second_handoff["ok"] is True
    assert second_handoff["applied"] is False
    assert second_handoff["status"] == "already_escalation_handoff_recorded"
    assert len(second_handoff["event"]["deadletter_escalation_handoffs"]) == 1

    premature_recovery = record_deadletter_recovery_request(
        deadletter_id,
        {
            "actor": "reactor.test",
            "reason": "recovery request should require acknowledgement first",
        },
    )
    assert premature_recovery["ok"] is False
    assert premature_recovery["applied"] is False
    assert premature_recovery["error"] == "deadletter_escalation_acknowledgement_required"

    acknowledgement = record_deadletter_escalation_acknowledgement(
        deadletter_id,
        {
            "actor": "reactor.test",
            "reason": "operator acknowledged the escalation handoff",
        },
    )

    assert acknowledgement["ok"] is True
    assert acknowledgement["applied"] is True
    assert acknowledgement["status"] == "deadletter_escalation_acknowledged"
    acknowledged_event = acknowledgement["event"]
    assert acknowledged_event["stable_state"] == "deadletter_escalation_acknowledged"
    assert acknowledged_event["dispatch"]["deadletter_escalation_acknowledged"] is True
    acknowledgement_receipt = acknowledged_event["latest_deadletter_escalation_acknowledgement_receipt"]
    assert acknowledgement_receipt["kind"] == "reactor.deadletter.escalation_acknowledgement.receipt"
    assert acknowledgement_receipt["deadletter_id"] == deadletter_id
    assert acknowledgement_receipt["status"] == "acknowledged"
    assert acknowledgement_receipt["route"] == "deadletter_escalation_acknowledgement"
    assert acknowledgement_receipt["stable_state"] == "deadletter_escalation_acknowledged"
    assert acknowledgement_receipt["source_receipt_kind"] == "reactor.deadletter.escalation_handoff.receipt"
    assert acknowledgement_receipt["escalation_acknowledged"] is True
    assert acknowledgement_receipt["external_escalation_started"] is False
    assert acknowledgement_receipt["recovery_started"] is False
    assert acknowledgement_receipt["retry_started"] is False
    assert acknowledgement_receipt["execution_started"] is False
    assert acknowledgement_receipt["escalation_started"] is False
    assert acknowledgement_receipt["memory_write"] is False
    assert acknowledgement_receipt["governance"]["execution_authority"] is False
    assert acknowledgement_receipt["governance"]["retry_authority"] is False
    assert acknowledgement_receipt["governance"]["escalation_authority"] is False
    assert acknowledgement_receipt["governance"]["memory_write"] is False
    assert acknowledged_event["latest_receipt"]["kind"] == "reactor.deadletter.escalation_acknowledgement.receipt"
    assert acknowledged_event["latest_deadletter_item"]["status"] == "escalation_acknowledged"
    assert acknowledged_event["deadletter_escalation_acknowledgements"][0]["deadletter_id"] == deadletter_id
    assert acknowledged_event["decision_journal"][-1]["kind"] == "reactor.deadletter.escalation_acknowledged"
    assert acknowledged_event["decision_journal"][-1]["applied"] is True
    assert acknowledged_event["decision_journal"][-1]["execution_started"] is False
    assert acknowledged_event["decision_journal"][-1]["escalation_started"] is False
    assert acknowledged_event["governance"]["deadletter_escalation_acknowledged"] is True
    assert acknowledged_event["governance"]["execution_authority"] is False
    assert acknowledged_event["governance"]["escalation_authority"] is False

    acknowledged_deadletter = get_deadletter(deadletter_id)
    assert acknowledged_deadletter is not None
    assert acknowledged_deadletter["status"] == "escalation_acknowledged"
    assert acknowledged_deadletter["latest_escalation_acknowledgement_receipt"]["deadletter_id"] == deadletter_id
    assert [item["deadletter_id"] for item in list_deadletters(status="escalation_acknowledged")] == [deadletter_id]
    assert {item["event_id"] for item in list_events(stable_state="deadletter_escalation_acknowledged")} == {
        str(created["event_id"])
    }
    assert {item["event_id"] for item in list_events(review_route="deadletter_escalation_acknowledgement")} == {
        str(created["event_id"])
    }
    assert {
        item["event_id"] for item in list_events(receipt_kind="reactor.deadletter.escalation_acknowledgement.receipt")
    } == {str(created["event_id"])}

    acknowledgement_review_queue = reactor_review_queue(route="deadletter_escalation_acknowledgement")
    assert acknowledgement_review_queue["available_total"] == 1
    assert (
        acknowledgement_review_queue["items"][0]["review"]["action"]
        == "wait_for_explicit_recovery_execution_boundary_after_acknowledgement"
    )
    acknowledged_status = reactor_status()
    assert acknowledged_status["stable_state_counts"] == {"deadletter_escalation_acknowledged": 1}
    assert acknowledged_status["deadletter_queue_counts"] == {"escalation_acknowledged": 1}
    assert acknowledged_status["deadletter_review_counts"] == {"reviewed": 1}
    assert acknowledged_status["deadletter_resolution_counts"] == {"escalation_pending": 1}
    assert acknowledged_status["deadletter_escalation_handoff_counts"] == {"handoff_recorded": 1}
    assert acknowledged_status["deadletter_escalation_acknowledgement_counts"] == {"acknowledged": 1}

    second_acknowledgement = record_deadletter_escalation_acknowledgement(
        deadletter_id,
        {
            "actor": "reactor.test",
            "reason": "same acknowledgement should not duplicate receipts",
        },
    )

    assert second_acknowledgement["ok"] is True
    assert second_acknowledgement["applied"] is False
    assert second_acknowledgement["status"] == "already_escalation_acknowledged"
    assert len(second_acknowledgement["event"]["deadletter_escalation_acknowledgements"]) == 1

    external_attempt = record_deadletter_external_escalation_attempt(
        deadletter_id,
        {
            "actor": "reactor.test",
            "reason": "record external escalation attempt without delivery",
            "external_channel": "ops_bridge",
            "external_target": "on_call",
            "external_adapter": "pager_stub",
        },
    )

    assert external_attempt["ok"] is True
    assert external_attempt["applied"] is True
    assert external_attempt["status"] == "deadletter_external_escalation_attempt_recorded"
    external_event = external_attempt["event"]
    assert external_event["stable_state"] == "deadletter_external_escalation_attempt_recorded"
    assert external_event["dispatch"]["deadletter_external_escalation_attempt_recorded"] is True
    assert external_event["dispatch"]["external_escalation_started"] is False
    assert external_event["dispatch"]["external_delivery_started"] is False
    external_receipt = external_event["latest_deadletter_external_escalation_attempt_receipt"]
    assert external_receipt["kind"] == "reactor.deadletter.external_escalation_attempt.receipt"
    assert external_receipt["deadletter_id"] == deadletter_id
    assert external_receipt["status"] == "attempt_recorded"
    assert external_receipt["route"] == "deadletter_external_escalation_attempt"
    assert external_receipt["stable_state"] == "deadletter_external_escalation_attempt_recorded"
    assert external_receipt["source_receipt_kind"] == "reactor.deadletter.escalation_acknowledgement.receipt"
    assert external_receipt["external_channel"] == "ops_bridge"
    assert external_receipt["external_target"] == "on_call"
    assert external_receipt["external_adapter"] == "pager_stub"
    assert external_receipt["external_adapter_declared"] is True
    assert external_receipt["external_adapter_known"] is False
    assert external_receipt["external_adapter_configured"] is False
    assert external_receipt["external_adapter_status"] == "not_configured"
    assert external_receipt["external_delivery_mode"] == "unsupported"
    assert external_receipt["external_delivery_ready"] is False
    assert external_receipt["external_delivery_queued"] is False
    assert external_receipt["external_delivery_blocker"] == "unsupported_external_adapter"
    assert external_receipt["missing_requirements"] == ["supported_external_adapter"]
    assert external_receipt["external_escalation_attempt_recorded"] is True
    assert external_receipt["external_escalation_started"] is False
    assert external_receipt["external_delivery_started"] is False
    assert external_receipt["execution_started"] is False
    assert external_receipt["dispatch_applied"] is False
    assert external_receipt["completion_claim_allowed"] is False
    assert external_receipt["memory_write"] is False
    assert external_receipt["governance"]["execution_authority"] is False
    assert external_receipt["governance"]["external_escalation_authority"] is False
    assert external_receipt["governance"]["escalation_authority"] is False
    assert external_event["latest_receipt"]["kind"] == "reactor.deadletter.external_escalation_attempt.receipt"
    assert external_event["latest_deadletter_item"]["status"] == "external_escalation_attempt_recorded"
    assert external_event["deadletter_external_escalation_attempts"][0]["deadletter_id"] == deadletter_id
    assert external_event["decision_journal"][-1]["kind"] == "reactor.deadletter.external_escalation_attempt_recorded"
    assert external_event["decision_journal"][-1]["external_delivery_started"] is False
    assert external_event["decision_journal"][-1]["external_adapter_configured"] is False
    assert external_event["decision_journal"][-1]["external_delivery_ready"] is False
    assert external_event["decision_journal"][-1]["dispatch_applied"] is False
    assert external_event["governance"]["deadletter_external_escalation_attempt_recorded"] is True
    assert external_event["governance"]["external_escalation_authority"] is False
    assert external_event["governance"]["external_delivery_authority"] is False

    external_deadletter = get_deadletter(deadletter_id)
    assert external_deadletter is not None
    assert external_deadletter["status"] == "external_escalation_attempt_recorded"
    assert external_deadletter["latest_external_escalation_attempt_receipt"]["deadletter_id"] == deadletter_id
    assert [item["deadletter_id"] for item in list_deadletters(status="external_escalation_attempt_recorded")] == [
        deadletter_id
    ]
    assert {
        item["event_id"] for item in list_events(stable_state="deadletter_external_escalation_attempt_recorded")
    } == {str(created["event_id"])}
    assert {item["event_id"] for item in list_events(review_route="deadletter_external_escalation_attempt")} == {
        str(created["event_id"])
    }
    assert {
        item["event_id"] for item in list_events(receipt_kind="reactor.deadletter.external_escalation_attempt.receipt")
    } == {str(created["event_id"])}

    external_review_queue = reactor_review_queue(route="deadletter_external_escalation_attempt")
    assert external_review_queue["available_total"] == 1
    assert (
        external_review_queue["items"][0]["review"]["action"]
        == "queue_recovery_request_or_configure_external_escalation_adapter_before_delivery"
    )
    external_status = reactor_status()
    assert external_status["stable_state_counts"] == {"deadletter_external_escalation_attempt_recorded": 1}
    assert external_status["deadletter_queue_counts"] == {"external_escalation_attempt_recorded": 1}
    assert external_status["deadletter_escalation_handoff_counts"] == {"handoff_recorded": 1}
    assert external_status["deadletter_escalation_acknowledgement_counts"] == {"acknowledged": 1}
    assert external_status["deadletter_external_escalation_attempt_counts"] == {"attempt_recorded": 1}

    blocked_delivery = record_deadletter_external_escalation_delivery(
        deadletter_id,
        {
            "actor": "reactor.test",
            "reason": "unsupported adapters must not queue local outbox delivery",
        },
    )
    assert blocked_delivery["ok"] is False
    assert blocked_delivery["applied"] is False
    assert blocked_delivery["error"] == "local_outbox_external_escalation_adapter_required"

    second_external_attempt = record_deadletter_external_escalation_attempt(
        deadletter_id,
        {
            "actor": "reactor.test",
            "reason": "same external attempt should not duplicate receipts",
        },
    )

    assert second_external_attempt["ok"] is True
    assert second_external_attempt["applied"] is False
    assert second_external_attempt["status"] == "already_external_escalation_attempt_recorded"
    assert len(second_external_attempt["event"]["deadletter_external_escalation_attempts"]) == 1

    recovery_request = record_deadletter_recovery_request(
        deadletter_id,
        {
            "actor": "reactor.test",
            "reason": "queue recovery through the existing operation dispatch gate",
        },
    )

    assert recovery_request["ok"] is True
    assert recovery_request["applied"] is True
    assert recovery_request["status"] == "deadletter_recovery_requested"
    recovered_event = recovery_request["event"]
    assert recovered_event["stable_state"] == "deadletter_recovery_requested"
    assert recovered_event["dispatch"]["deadletter_recovery_requested"] is True
    assert recovered_event["dispatch"]["recovery_operation_id"] == operation_id
    recovery_receipt = recovered_event["latest_deadletter_recovery_request_receipt"]
    recovery_event_id = recovery_receipt["recovery_event_id"]
    assert recovery_receipt["kind"] == "reactor.deadletter.recovery_request.receipt"
    assert recovery_receipt["deadletter_id"] == deadletter_id
    assert recovery_receipt["status"] == "recovery_requested"
    assert recovery_receipt["route"] == "deadletter_recovery_request"
    assert recovery_receipt["stable_state"] == "deadletter_recovery_requested"
    assert recovery_receipt["source_receipt_kind"] == "reactor.deadletter.external_escalation_attempt.receipt"
    assert recovery_receipt["external_escalation_attempt_receipt_id"] == external_receipt["receipt_id"]
    assert recovery_receipt["operation_id"] == operation_id
    assert recovery_receipt["recovery_requested"] is True
    assert recovery_receipt["recovery_event_enqueued"] is True
    assert recovery_receipt["external_escalation_started"] is False
    assert recovery_receipt["recovery_started"] is False
    assert recovery_receipt["retry_started"] is False
    assert recovery_receipt["execution_started"] is False
    assert recovery_receipt["escalation_started"] is False
    assert recovery_receipt["memory_write"] is False
    assert recovery_receipt["governance"]["execution_authority"] is False
    assert recovery_receipt["governance"]["dispatch_authority"] is False
    assert recovery_receipt["governance"]["recovery_request_authority"] is True
    assert recovery_receipt["governance"]["memory_write"] is False
    assert recovered_event["latest_receipt"]["kind"] == "reactor.deadletter.recovery_request.receipt"
    assert recovered_event["latest_deadletter_item"]["status"] == "recovery_requested"
    assert recovered_event["deadletter_recovery_requests"][0]["deadletter_id"] == deadletter_id
    assert recovered_event["decision_journal"][-1]["kind"] == "reactor.deadletter.recovery_requested"
    assert recovered_event["decision_journal"][-1]["recovery_event_enqueued"] is True
    assert recovered_event["decision_journal"][-1]["execution_started"] is False
    assert recovered_event["governance"]["deadletter_recovery_requested"] is True
    assert recovered_event["governance"]["execution_authority"] is False
    assert recovered_event["governance"]["dispatch_authority"] is False

    queued_recovery = recovery_request["recovery_event"]
    assert queued_recovery["event_id"] == recovery_event_id
    assert queued_recovery["status"] == "queued"
    assert queued_recovery["stable_state"] == "awaiting_dispatch"
    assert queued_recovery["trigger"]["source"] == "deadletter_recovery"
    assert queued_recovery["trigger"]["type"] == "deadletter_recovery_request"
    assert queued_recovery["trigger"]["operation_id"] == operation_id
    assert queued_recovery["trigger"]["metadata"]["deadletter_id"] == deadletter_id
    assert queued_recovery["classification"]["action_class"] == "operation_run"
    assert queued_recovery["dispatch"]["applied"] is False
    assert queued_recovery["governance"]["execution_authority"] is False
    assert get_event(recovery_event_id)["trigger"]["operation_id"] == operation_id  # type: ignore[index]

    requested_deadletter = get_deadletter(deadletter_id)
    assert requested_deadletter is not None
    assert requested_deadletter["status"] == "recovery_requested"
    assert requested_deadletter["latest_recovery_request_receipt"]["recovery_event_id"] == recovery_event_id
    assert [item["deadletter_id"] for item in list_deadletters(status="recovery_requested")] == [deadletter_id]
    assert {item["event_id"] for item in list_events(stable_state="deadletter_recovery_requested")} == {
        str(created["event_id"])
    }
    assert {item["event_id"] for item in list_events(review_route="deadletter_recovery_request")} == {
        str(created["event_id"])
    }
    assert {item["event_id"] for item in list_events(trigger_source="deadletter_recovery")} == {recovery_event_id}
    assert {item["event_id"] for item in list_events(receipt_kind="reactor.deadletter.recovery_request.receipt")} == {
        str(created["event_id"])
    }

    recovery_review_queue = reactor_review_queue(route="deadletter_recovery_request")
    assert recovery_review_queue["available_total"] == 1
    assert (
        recovery_review_queue["items"][0]["review"]["action"] == "record_dispatch_attempt_for_deadletter_recovery_event"
    )
    assert reactor_review_queue(route="deadletter_escalation_acknowledgement")["available_total"] == 0
    assert reactor_review_queue(route="deadletter_external_escalation_attempt")["available_total"] == 0
    recovery_status = reactor_status()
    assert recovery_status["stable_state_counts"] == {
        "deadletter_recovery_requested": 1,
        "awaiting_dispatch": 1,
    }
    assert recovery_status["deadletter_queue_counts"] == {"recovery_requested": 1}
    assert recovery_status["deadletter_external_escalation_attempt_counts"] == {"attempt_recorded": 1}
    assert recovery_status["deadletter_recovery_request_counts"] == {"recovery_requested": 1}

    second_recovery_request = record_deadletter_recovery_request(
        deadletter_id,
        {
            "actor": "reactor.test",
            "reason": "same recovery request should not duplicate receipts",
        },
    )
    assert second_recovery_request["ok"] is True
    assert second_recovery_request["applied"] is False
    assert second_recovery_request["status"] == "already_recovery_requested"
    assert len(second_recovery_request["event"]["deadletter_recovery_requests"]) == 1

    monkeypatch.setenv("FRANCIS_API_ACTOR_SCOPES", json.dumps({"reactor.test": ["operations.run"]}))
    recovery_dispatch = record_dispatch_attempt(
        recovery_event_id,
        {
            "actor": "reactor.test",
            "reason": "dispatch queued deadletter recovery through the existing operation gate",
        },
    )

    assert recovery_dispatch["ok"] is True
    assert recovery_dispatch["applied"] is True
    dispatched_recovery = recovery_dispatch["event"]
    assert dispatched_recovery["event_id"] == recovery_event_id
    assert dispatched_recovery["trigger"]["source"] == "deadletter_recovery"
    assert dispatched_recovery["trigger"]["operation_id"] == operation_id
    assert dispatched_recovery["trigger"]["metadata"]["deadletter_id"] == deadletter_id
    assert dispatched_recovery["trigger"]["metadata"]["source_event_id"] == str(created["event_id"])
    assert dispatched_recovery["status"] == "dispatch_completed"
    assert dispatched_recovery["stable_state"] == "dispatch_succeeded"
    assert dispatched_recovery["dispatch"]["engine"] == "operation_run"
    assert dispatched_recovery["dispatch"]["applied"] is True
    assert dispatched_recovery["dispatch"]["execution_started"] is True
    recovery_execution = dispatched_recovery["latest_dispatch_execution_receipt"]
    assert recovery_execution["kind"] == "reactor.dispatch.execution.receipt"
    assert recovery_execution["operation_id"] == operation_id
    assert recovery_execution["status"] == "completed"
    assert recovery_execution["outcome"] == "operation_succeeded"
    assert recovery_execution["execution_started"] is True
    assert recovery_execution["dispatch_applied"] is True
    assert recovery_execution["verified"] is True
    assert recovery_execution["governance"]["authority_source"] == "operations.run"
    assert recovery_execution["governance"]["approval_authority"] is False
    assert recovery_execution["governance"]["memory_write"] is False
    recovery_verification = dispatched_recovery["latest_verification_receipt"]
    assert recovery_verification["verification_status"] == "passed"
    assert recovery_verification["verification_outcome"] == "operation_succeeded"
    assert recovery_verification["source_receipt_kind"] == "reactor.dispatch.execution.receipt"
    assert recovery_verification["operation_id"] == operation_id
    assert recovery_verification["verified"] is True
    assert recovery_verification["completion_claim_allowed"] is True
    recovery_stable_return = dispatched_recovery["latest_stable_return"]
    assert recovery_stable_return["route"] == "operation_run"
    assert recovery_stable_return["stable_state"] == "dispatch_succeeded"
    assert recovery_stable_return["source_receipt_kind"] == "reactor.dispatch.execution.receipt"
    assert recovery_stable_return["operation_id"] == operation_id
    assert recovery_stable_return["dispatch_applied"] is True
    assert recovery_stable_return["execution_started"] is True
    recovery_settlement = recovery_dispatch["deadletter_recovery_dispatch"]
    recovery_settlement_receipt = recovery_settlement["receipt"]
    assert recovery_settlement_receipt["kind"] == "reactor.deadletter.recovery_dispatch.receipt"
    assert recovery_settlement_receipt["deadletter_id"] == deadletter_id
    assert recovery_settlement_receipt["status"] == "recovery_dispatched"
    assert recovery_settlement_receipt["route"] == "deadletter_recovery_dispatch"
    assert recovery_settlement_receipt["stable_state"] == "deadletter_recovery_dispatched"
    assert recovery_settlement_receipt["recovery_event_id"] == recovery_event_id
    assert recovery_settlement_receipt["operation_id"] == operation_id
    assert recovery_settlement_receipt["operation_status"] == "succeeded"
    assert recovery_settlement_receipt["source_receipt_kind"] == "reactor.dispatch.execution.receipt"
    assert recovery_settlement_receipt["recovery_dispatched"] is True
    assert recovery_settlement_receipt["deadletter_settled"] is True
    assert recovery_settlement_receipt["execution_started"] is True
    assert recovery_settlement_receipt["dispatch_applied"] is True
    assert recovery_settlement_receipt["governance"]["authority_source"] == "operations.run"
    assert recovery_settlement_receipt["governance"]["deadletter_settlement_authority"] is True
    assert recovery_settlement_receipt["governance"]["approval_authority"] is False
    assert recovery_settlement_receipt["governance"]["promotion_authority"] is False
    assert recovery_settlement["item"]["status"] == "recovery_dispatched"
    assert recovery_settlement["source_event"]["stable_state"] == "deadletter_recovery_dispatched"
    assert (
        recovery_settlement["source_event"]["latest_deadletter_recovery_dispatch_receipt"]["deadletter_id"]
        == deadletter_id
    )
    assert {item["event_id"] for item in list_events(stable_state="dispatch_succeeded")} == {recovery_event_id}
    assert {item["event_id"] for item in list_events(receipt_kind="reactor.dispatch.execution.receipt")} == {
        recovery_event_id
    }
    assert {item["event_id"] for item in list_events(stable_state="deadletter_recovery_dispatched")} == {
        str(created["event_id"])
    }
    assert {item["event_id"] for item in list_events(receipt_kind="reactor.deadletter.recovery_dispatch.receipt")} == {
        str(created["event_id"])
    }
    assert {item["event_id"] for item in list_events(review_route="deadletter_recovery_dispatch")} == {
        str(created["event_id"])
    }
    assert reactor_review_queue(route="deadletter_recovery_request")["available_total"] == 0
    recovered_deadletter = get_deadletter(deadletter_id)
    assert recovered_deadletter is not None
    assert recovered_deadletter["status"] == "recovery_dispatched"
    assert recovered_deadletter["recovery_event_id"] == recovery_event_id
    assert (
        recovered_deadletter["latest_recovery_dispatch_receipt"]["receipt_id"]
        == recovery_settlement_receipt["receipt_id"]
    )
    recovery_receipts = list_deadletter_recovery_receipts(deadletter_id=deadletter_id)
    assert [item["receipt_kind"] for item in recovery_receipts] == [
        "reactor.deadletter.recovery_dispatch.receipt",
        "reactor.deadletter.recovery_request.receipt",
    ]
    assert {item["route"] for item in recovery_receipts} == {
        "deadletter_recovery_request",
        "deadletter_recovery_dispatch",
    }
    assert {item["recovery_event_id"] for item in recovery_receipts} == {recovery_event_id}
    assert all(item["governance"]["execution_authority"] is False for item in recovery_receipts)
    dispatch_receipts = list_deadletter_recovery_receipts(route="deadletter_recovery_dispatch")
    assert [item["receipt_id"] for item in dispatch_receipts] == [recovery_settlement_receipt["receipt_id"]]
    fetched_recovery_dispatch = get_deadletter_recovery_receipt(recovery_settlement_receipt["receipt_id"])
    assert fetched_recovery_dispatch is not None
    assert fetched_recovery_dispatch["deadletter_id"] == deadletter_id
    assert fetched_recovery_dispatch["status"] == "recovery_dispatched"
    assert fetched_recovery_dispatch["source_governance"]["execution_authority"] is True
    assert fetched_recovery_dispatch["governance"]["execution_authority"] is False
    assert get_deadletter_recovery_receipt("missing_recovery_receipt") is None
    assert [item["deadletter_id"] for item in list_deadletters(status="recovery_requested")] == []
    assert [item["deadletter_id"] for item in list_deadletters(status="recovery_dispatched")] == [deadletter_id]
    recovery_dispatch_status = reactor_status()
    assert recovery_dispatch_status["stable_state_counts"] == {
        "deadletter_recovery_dispatched": 1,
        "dispatch_succeeded": 1,
    }
    assert recovery_dispatch_status["dispatch_execution_counts"] == {"completed": 1}
    assert recovery_dispatch_status["verification_counts"] == {"not_run": 1, "passed": 1}
    assert recovery_dispatch_status["verification_outcome_counts"] == {
        "deadletter_queued_for_review": 1,
        "operation_succeeded": 1,
    }
    assert recovery_dispatch_status["deadletter_queue_counts"] == {"recovery_dispatched": 1}
    assert recovery_dispatch_status["deadletter_recovery_request_counts"] == {"recovery_requested": 1}
    assert recovery_dispatch_status["deadletter_recovery_dispatch_counts"] == {"recovery_dispatched": 1}

    operation_detail = operations_runtime.get_operation_detail(operation_id)
    assert operation_detail["operation"]["status"] == "succeeded"


def test_reactor_dispatch_attempt_rejects_missing_event(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    missing = record_dispatch_attempt("reactor_evt_missing", {"actor": "reactor.test"})

    assert missing == {"ok": False, "applied": False, "error": "not_found", "event": None}
    assert not (data_root / "reactor" / "events").exists()
