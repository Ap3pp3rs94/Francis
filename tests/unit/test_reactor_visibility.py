from __future__ import annotations

from pathlib import Path

from francis.operations import runtime as operations_runtime
from francis.reactor.events import (
    enqueue_event,
    record_deadletter_escalation_acknowledgement,
    record_deadletter_escalation_handoff,
    record_deadletter_external_escalation_attempt,
    record_deadletter_external_escalation_delivery,
    record_deadletter_external_escalation_delivery_processor_completion,
    record_deadletter_external_escalation_delivery_processor_handoff,
    record_deadletter_resolution,
    record_deadletter_review,
    record_dispatch_attempt,
)
from francis.reactor.visibility import reactor_operator_visibility_summary


def test_reactor_operator_visibility_summary_surfaces_external_sender_readiness(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "francis_data"))
    operation = operations_runtime.create_operation(
        action="plan.create",
        reason="reactor visibility should summarize external sender blockers",
        input={"goal": "prove external sender readiness visibility"},
        actor="reactor.test",
    )
    operation_id = str(operation["operation_id"])

    created = enqueue_event(
        {
            "trigger_source": "mission_queue",
            "summary": "Visibility should show blocked external sender readiness.",
            "action_class": "classify",
            "operation_id": operation_id,
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
            "reason": "operator wants escalation tracked before sender visibility",
        },
    )
    record_deadletter_escalation_handoff(
        deadletter_id,
        {
            "actor": "reactor.test",
            "reason": "record external handoff before sender visibility",
        },
    )
    record_deadletter_escalation_acknowledgement(
        deadletter_id,
        {
            "actor": "reactor.test",
            "reason": "operator acknowledged the escalation handoff",
        },
    )
    record_deadletter_external_escalation_attempt(
        deadletter_id,
        {
            "actor": "reactor.test",
            "reason": "preflight local outbox without sending externally",
            "external_channel": "ops_bridge",
            "external_target": "on_call",
            "external_adapter": "local-outbox",
        },
    )
    delivery = record_deadletter_external_escalation_delivery(
        deadletter_id,
        {
            "actor": "reactor.test",
            "reason": "queue local outbox delivery without external send authority",
        },
    )
    delivery_id = str(delivery["receipt"]["delivery_id"])
    record_deadletter_external_escalation_delivery_processor_handoff(
        delivery_id,
        {
            "actor": "reactor.test",
            "reason": "record processor handoff without claiming external send",
        },
    )
    record_deadletter_external_escalation_delivery_processor_completion(
        delivery_id,
        {
            "actor": "reactor.test",
            "reason": "complete local processor without external send",
        },
    )

    summary = reactor_operator_visibility_summary(limit=5)

    assert summary["ok"] is True
    assert summary["kind"] == "reactor.operator_visibility.summary"
    assert summary["external_delivery_total"] == 1
    assert summary["external_delivery_sender_readiness_total"] == 1
    assert summary["external_delivery_sender_contract_status"] == "blocked"
    assert summary["external_delivery_sender_contract_ready"] is False
    assert summary["external_delivery_sender_contract_blocker"] == "external_sender_adapter_contract_missing"
    assert summary["supported_external_sender_adapters"] == []
    assert summary["supported_external_sender_adapter_total"] == 0
    assert summary["external_sender_required_fields"] == [
        "local_outbox_processor_completion",
        "external_sender_adapter",
        "external_sender_channel",
        "external_sender_target",
    ]
    assert summary["attention"]["ready_external_delivery_sender_total"] == 0
    assert summary["attention"]["blocked_external_delivery_sender_total"] == 1
    assert summary["attention"]["external_delivery_sender_contract_ready_total"] == 0
    assert summary["attention"]["external_delivery_sender_contract_blocked_total"] == 1
    assert summary["counts"]["delivery_sender_status"] == {"blocked": 1}
    assert summary["counts"]["external_delivery_sender_contract"] == {"blocked": 1}
    assert (
        summary["readback_surfaces"]["external_delivery_sender_readiness"]
        == "/reactor/deadletters/external_escalation_deliveries/sender_readiness/list"
    )
    assert (
        summary["readback_surfaces"]["external_delivery_sender_contract"]
        == "/reactor/deadletters/external_escalation_deliveries/sender_contract"
    )
    assert summary["external_delivery_sender_contract"]["external_delivery_sender_ready"] is False
    assert summary["external_delivery_sender_contract"]["completion_claim_allowed"] is False
    assert summary["external_delivery_sender_contract"]["governance"]["external_delivery_authority"] is False
    assert summary["external_delivery_sender_contract"]["governance"]["external_escalation_authority"] is False
    assert summary["ready_external_delivery_sender_items"] == []

    blocked_items = summary["blocked_external_delivery_sender_items"]
    assert len(blocked_items) == 1
    blocked = blocked_items[0]
    assert blocked["delivery_id"] == delivery_id
    assert blocked["external_delivery_sender_ready"] is False
    assert blocked["external_delivery_sender_blockers"] == ["external_sender_adapter"]
    assert blocked["external_delivery_started"] is False
    assert blocked["external_network_send"] is False
    assert blocked["governance"]["external_delivery_authority"] is False
    assert summary["governance"]["external_delivery_authority"] is False
    assert summary["governance"]["external_escalation_authority"] is False
