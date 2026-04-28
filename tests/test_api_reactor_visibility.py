from __future__ import annotations

import json
from pathlib import Path

_REACTOR_ACTOR = "test.reactor.visibility.api"


def _write_proposal(data_root: Path, *, proposal_id: str, plugin_id: str) -> None:
    proposal_path = data_root / "artifacts" / "plugins" / "proposals" / f"{proposal_id}.json"
    proposal_path.parent.mkdir(parents=True, exist_ok=True)
    proposal_path.write_text(
        json.dumps(
            {
                "kind": "plugin.proposal",
                "proposal_id": proposal_id,
                "plugin_id": plugin_id,
                "status": "staged",
                "friction": {
                    "summary": "API Reactor operator visibility needs one truthful summary.",
                    "evidence": ["reactor.visibility.api.repeat"],
                },
                "quality_requirements": {
                    "tests": ["tests/test_api_reactor_visibility.py"],
                    "docs": ["docs/operations/COMPLETION_LEDGER.md"],
                    "risk_tier": "normal",
                    "validation_path": ["python -m pytest tests/test_api_reactor_visibility.py"],
                    "known_limits": ["backend readback only"],
                },
                "review": {
                    "status": "approved",
                    "receipt_id": "proposal_review_visibility_summary_api",
                },
                "validation": {
                    "validation_receipt_id": "validation_visibility_summary_api",
                    "validation_receipt_path": (
                        "data/artifacts/plugins/validations/validation_visibility_summary_api.json"
                    ),
                },
            }
        ),
        encoding="utf-8",
    )


def test_reactor_operator_visibility_summary_route_is_read_only(
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
            "summary": "Approval-gated API mutation needs operator visibility.",
            "risk_tier": "critical",
            "action_class": "mutate",
            "approval_required": True,
            "approval_id": "appr_visibility_summary_api",
            "actor": _REACTOR_ACTOR,
        },
    )
    assert queued.status_code == 200
    approval_id = str(queued.json()["event_id"])
    attempted = client.post(
        "/reactor/events/dispatch_attempt",
        json={"event_id": approval_id, "actor": _REACTOR_ACTOR},
    )
    assert attempted.status_code == 200
    assert attempted.json()["event"]["stable_state"] == "awaiting_approval"

    plugin = client.post(
        "/reactor/events/enqueue",
        json={
            "trigger_source": "user_request",
            "summary": "API plugin run boundary needs operator visibility without execution.",
            "mode": "pilot",
            "actor": _REACTOR_ACTOR,
            "action_class": "plugin_run",
            "metadata": {"plugin_id": "generated.visibility_boundary_api"},
        },
    )
    assert plugin.status_code == 200
    plugin_event_id = str(plugin.json()["event_id"])
    plugin_attempt = client.post(
        "/reactor/events/dispatch_attempt",
        json={
            "event_id": plugin_event_id,
            "actor": _REACTOR_ACTOR,
            "reason": "prove plugin boundary visibility through API summary",
        },
    )
    assert plugin_attempt.status_code == 200
    plugin_attempt_body = plugin_attempt.json()
    assert plugin_attempt_body["event"]["stable_state"] == "plugin_run_dispatch_not_enabled"
    assert plugin_attempt_body["event"]["dispatch"]["dispatch_execution_receipt"]["plugin_execution_started"] is False

    proposal_id = "plugin_proposal_visibility_summary_api"
    plugin_id = "generated.visibility_summary_api"
    _write_proposal(data_root, proposal_id=proposal_id, plugin_id=plugin_id)
    proposal = client.post(
        "/reactor/events/enqueue",
        json={
            "trigger_source": "forge_proposal",
            "summary": "Inspect Forge proposal visibility through the API.",
            "mode": "pilot",
            "actor": _REACTOR_ACTOR,
            "max_actions": 1,
            "metadata": {"proposal_id": proposal_id},
        },
    )
    assert proposal.status_code == 200
    proposal_event_id = str(proposal.json()["event_id"])
    proposal_attempt = client.post(
        "/reactor/events/dispatch_attempt",
        json={
            "event_id": proposal_event_id,
            "actor": _REACTOR_ACTOR,
            "reason": "read proposal quality without deciding or promoting it",
        },
    )
    assert proposal_attempt.status_code == 200
    assert proposal_attempt.json()["event"]["stable_state"] == "proposal_review_inspected"

    response = client.get("/reactor/operator_visibility/summary", params={"limit": 5})

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["kind"] == "reactor.operator_visibility.summary"
    assert body["event_total"] == 3
    assert body["review_queue_total"] == 2
    assert body["dispatch_engine"] == "partial"
    assert "dispatch" in body["dispatch_engine_boundary_actions"]
    assert "execute" in body["dispatch_engine_boundary_actions"]
    assert "mutate" in body["dispatch_engine_boundary_actions"]
    assert "plugin_run" in body["dispatch_engine_boundary_actions"]
    assert body["dispatch_engine_boundary_action_total"] == 4
    assert body["attention"]["dispatch_engine_boundary_action_total"] == 4
    assert body["proposal_review_history_total"] == 1
    assert body["external_delivery_sender_contract_status"] == "blocked"
    assert body["external_delivery_sender_contract_ready"] is False
    assert body["external_delivery_sender_contract_blocker"] == "external_sender_adapter_contract_missing"
    assert body["bounded_plan_trace_total"] == 3
    assert body["bounded_plan_dispatch_linked_total"] == 3
    assert body["bounded_plan_dispatch_pending_total"] == 0
    assert body["bounded_plan_dispatch_unlinked_total"] == 0
    assert body["reflection_receipt_total"] == 3
    assert body["supported_external_sender_adapters"] == []
    assert body["supported_external_sender_adapter_total"] == 0
    assert body["external_sender_required_fields"] == [
        "local_outbox_processor_completion",
        "external_sender_adapter",
        "external_sender_channel",
        "external_sender_target",
    ]
    assert body["attention"]["external_delivery_sender_contract_ready_total"] == 0
    assert body["attention"]["external_delivery_sender_contract_blocked_total"] == 1
    assert body["attention"]["bounded_plan_dispatch_pending_total"] == 0
    assert body["attention"]["bounded_plan_dispatch_unlinked_total"] == 0
    assert body["attention"]["proposal_review_ready_total"] == 1
    assert body["counts"]["review_route"] == {"approval_queue": 1, "operator_review": 1}
    assert body["counts"]["blocker_route"] == {"approval_queue": 1, "operator_review": 1}
    assert body["counts"]["approval_request"] == {}
    assert body["counts"]["dispatch_execution"] == {"blocked": 1, "completed": 1}
    assert body["counts"]["dispatch_engine_boundary_action"] == {
        "dispatch": 1,
        "execute": 1,
        "mutate": 1,
        "plugin_run": 1,
    }
    assert body["counts"]["verification"] == {"not_run": 2, "passed": 1}
    assert body["counts"]["verification_outcome"] == {
        "approval_required": 1,
        "plugin_run_dispatch_not_enabled": 1,
        "proposal_review_ready": 1,
    }
    assert body["counts"]["reflection"] == {"reflected": 3}
    assert body["counts"]["reflection_outcome"] == {
        "bounded_work_not_verified": 2,
        "bounded_work_verified": 1,
    }
    assert body["counts"]["stable_return"] == {"settled": 3}
    assert body["counts"]["bounded_plan_trace"] == {"dispatch_linked": 3}
    assert body["counts"]["external_delivery_sender_contract"] == {"blocked": 1}
    assert body["readback_surfaces"]["review_queue"] == "/reactor/review_queue"
    assert body["readback_surfaces"]["external_delivery_sender_contract"] == (
        "/reactor/deadletters/external_escalation_deliveries/sender_contract"
    )
    assert body["readback_surfaces"]["bounded_plan_events"] == (
        "/reactor/events/list?receipt_kind=reactor.bounded_plan.receipt"
    )
    assert body["readback_surfaces"]["bounded_plan_dispatch_traces"] == (
        "/reactor/events/list?receipt_kind=reactor.dispatch_attempt.receipt"
    )
    assert body["readback_surfaces"]["reflection_receipts"] == (
        "/reactor/events/list?receipt_kind=reactor.reflection.receipt"
    )
    assert body["external_delivery_sender_contract"]["external_delivery_sender_ready"] is False
    assert body["external_delivery_sender_contract"]["completion_claim_allowed"] is False
    assert body["external_delivery_sender_contract"]["governance"]["external_delivery_authority"] is False
    assert body["external_delivery_sender_contract"]["governance"]["external_escalation_authority"] is False
    bounded_plan_traces = {item["event_id"]: item for item in body["latest_bounded_plan_traces"]}
    assert set(bounded_plan_traces) == {approval_id, plugin_event_id, proposal_event_id}
    plugin_trace = bounded_plan_traces[plugin_event_id]
    assert plugin_trace["kind"] == "reactor.bounded_plan_trace.readback"
    assert plugin_trace["trace_status"] == "dispatch_linked"
    assert plugin_trace["dispatch_attempt_linked"] is True
    assert plugin_trace["bounded_plan_status"] == "planned"
    assert plugin_trace["dispatch_attempt_bounded_plan_receipt_id"] == plugin_trace["bounded_plan_receipt_id"]
    assert plugin_trace["execution_started"] is False
    assert plugin_trace["governance"]["execution_authority"] is False
    review_by_event_id = {item["event_id"]: item for item in body["latest_review_items"]}
    assert set(review_by_event_id) == {approval_id, plugin_event_id}
    plugin_review = review_by_event_id[plugin_event_id]
    assert plugin_review["classification"]["action_class"] == "plugin_run"
    assert plugin_review["review"]["route"] == "operator_review"
    assert plugin_review["review"]["receipt_kind"] == "reactor.dispatch_blocker"
    assert plugin_review["review"]["execution_started"] is False
    assert plugin_review["review"]["applied"] is False
    assert [item["event_id"] for item in body["latest_proposal_reviews"]] == [proposal_event_id]

    governance = body["governance"]
    assert governance["execution_authority"] is False
    assert governance["dispatch_authority"] is False
    assert governance["plugin_run_authority"] is False
    assert governance["approval_authority"] is False
    assert governance["retry_authority"] is False
    assert governance["external_delivery_authority"] is False
    assert governance["external_escalation_authority"] is False
    assert governance["proposal_decision_authority"] is False
    assert governance["promotion_authority"] is False
    assert governance["memory_write"] is False
