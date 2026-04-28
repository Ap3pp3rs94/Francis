from __future__ import annotations

import json
from pathlib import Path

from francis.reactor.events import enqueue_event, record_dispatch_attempt
from francis.reactor.visibility import reactor_operator_visibility_summary


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
                    "summary": "Repeated Reactor operator visibility needs one summary.",
                    "evidence": ["reactor.visibility.repeat"],
                },
                "quality_requirements": {
                    "tests": ["tests/unit/test_reactor_operator_visibility.py"],
                    "docs": ["docs/operations/COMPLETION_LEDGER.md"],
                    "risk_tier": "normal",
                    "validation_path": ["python -m pytest tests/unit/test_reactor_operator_visibility.py"],
                    "known_limits": ["backend readback only"],
                },
                "review": {
                    "status": "approved",
                    "receipt_id": "proposal_review_visibility_summary",
                },
                "validation": {
                    "validation_receipt_id": "validation_visibility_summary",
                    "validation_receipt_path": (
                        "data/artifacts/plugins/validations/validation_visibility_summary.json"
                    ),
                },
            }
        ),
        encoding="utf-8",
    )


def test_reactor_operator_visibility_summary_aggregates_readbacks_without_authority(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    actor = "test.reactor.visibility"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_API_ACTOR_SCOPES", json.dumps({actor: ["reactor.write"]}))

    approval_event = enqueue_event(
        {
            "trigger_source": "user_request",
            "summary": "Approval-gated mutation needs operator visibility.",
            "risk_tier": "critical",
            "action_class": "mutate",
            "approval_required": True,
            "approval_id": "appr_visibility_summary",
        }
    )
    approval_id = str(approval_event["event_id"])
    approval_attempt = record_dispatch_attempt(approval_id, {"actor": actor})
    assert approval_attempt["event"]["stable_state"] == "awaiting_approval"

    plugin_event = enqueue_event(
        {
            "trigger_source": "user_request",
            "summary": "Plugin run boundary needs operator visibility without execution.",
            "mode": "pilot",
            "actor": actor,
            "action_class": "plugin_run",
            "metadata": {"plugin_id": "generated.visibility_boundary"},
        }
    )
    plugin_event_id = str(plugin_event["event_id"])
    plugin_attempt = record_dispatch_attempt(
        plugin_event_id,
        {"actor": actor, "reason": "prove plugin run boundary is visible without execution"},
    )
    assert plugin_attempt["event"]["stable_state"] == "plugin_run_dispatch_not_enabled"
    assert plugin_attempt["event"]["dispatch"]["dispatch_execution_receipt"]["plugin_execution_started"] is False

    proposal_id = "plugin_proposal_visibility_summary"
    plugin_id = "generated.visibility_summary"
    _write_proposal(data_root, proposal_id=proposal_id, plugin_id=plugin_id)
    proposal_event = enqueue_event(
        {
            "trigger_source": "forge_proposal",
            "summary": "Inspect Forge proposal visibility through Reactor.",
            "mode": "pilot",
            "actor": actor,
            "max_actions": 1,
            "metadata": {"proposal_id": proposal_id},
        }
    )
    proposal_event_id = str(proposal_event["event_id"])
    proposal_attempt = record_dispatch_attempt(
        proposal_event_id,
        {"actor": actor, "reason": "read proposal quality without deciding or promoting"},
    )
    assert proposal_attempt["event"]["stable_state"] == "proposal_review_inspected"

    summary = reactor_operator_visibility_summary(limit=5)

    assert summary["ok"] is True
    assert summary["kind"] == "reactor.operator_visibility.summary"
    assert summary["status"] == "ready"
    assert summary["event_total"] == 3
    assert summary["review_queue_total"] == 2
    assert summary["dispatch_engine"] == "partial"
    assert "dispatch" in summary["dispatch_engine_boundary_actions"]
    assert "execute" in summary["dispatch_engine_boundary_actions"]
    assert "mutate" in summary["dispatch_engine_boundary_actions"]
    assert "plugin_run" in summary["dispatch_engine_boundary_actions"]
    assert summary["dispatch_engine_boundary_action_total"] == 4
    assert summary["attention"]["dispatch_engine_boundary_action_total"] == 4
    assert summary["proposal_review_history_total"] == 1
    assert summary["attention"]["review_queue_total"] == 2
    assert summary["attention"]["proposal_review_ready_total"] == 1
    assert summary["attention"]["proposal_review_blocked_total"] == 0
    assert summary["counts"]["review_route"] == {"approval_queue": 1, "operator_review": 1}
    assert summary["counts"]["dispatch_engine_boundary_action"] == {
        "dispatch": 1,
        "execute": 1,
        "mutate": 1,
        "plugin_run": 1,
    }
    assert summary["readback_surfaces"]["proposal_review_history"] == ("/reactor/proposal_reviews/history/list")
    review_by_event_id = {item["event_id"]: item for item in summary["latest_review_items"]}
    assert set(review_by_event_id) == {approval_id, plugin_event_id}
    plugin_review = review_by_event_id[plugin_event_id]
    assert plugin_review["classification"]["action_class"] == "plugin_run"
    assert plugin_review["review"]["route"] == "operator_review"
    assert plugin_review["review"]["receipt_kind"] == "reactor.dispatch_blocker"
    assert plugin_review["review"]["execution_started"] is False
    assert plugin_review["review"]["applied"] is False
    assert [item["event_id"] for item in summary["latest_proposal_reviews"]] == [proposal_event_id]

    governance = summary["governance"]
    assert governance["execution_authority"] is False
    assert governance["dispatch_authority"] is False
    assert governance["plugin_run_authority"] is False
    assert governance["approval_authority"] is False
    assert governance["deadletter_authority"] is False
    assert governance["deadletter_resolution_authority"] is False
    assert governance["retry_authority"] is False
    assert governance["external_delivery_authority"] is False
    assert governance["external_escalation_authority"] is False
    assert governance["proposal_decision_authority"] is False
    assert governance["promotion_authority"] is False
    assert governance["memory_write"] is False
