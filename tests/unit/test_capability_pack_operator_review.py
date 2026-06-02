from __future__ import annotations

from francis.economy.markets.capability_pack_operator_review import analyze_capability_pack_operator_review


def test_capability_pack_operator_review_projects_ready_staged_pack_for_review() -> None:
    analysis = analyze_capability_pack_operator_review(
        [
            {
                "capability": "generated.deploy",
                "version": "0.1.0",
                "source": "generated",
                "status": "staged",
                "risk_tier": "critical",
                "proposal_id": "plugin_proposal_generated_deploy",
                "quality": {"tests": ["tests/test_deploy.py"], "docs": ["docs/deploy.md"]},
                "metadata": {
                    "validation_receipt_id": "plugin_validation_generated_deploy",
                    "pack_id": "ops.deploy",
                    "pack_version": "1.0.0",
                    "pack_name": "Ops Deploy Pack",
                    "promotion_rules": [
                        "metadata_receipt_before_promotion",
                        "quality_standards_before_promotion",
                        "operator_review_before_promotion",
                    ],
                    "pack_governance": {
                        "risk_tier": "critical",
                        "operator_review_required": True,
                        "scope": "build_dev",
                    },
                },
            }
        ]
    )

    assert analysis["stage"] == "Stage 17 / Capability Economy"
    assert analysis["status"] == "ready_for_operator_review"
    assert analysis["pack_total"] == 1
    assert analysis["ready_pack_count"] == 1
    assert analysis["decision_required_pack_count"] == 1
    assert analysis["review_queue_count"] == 1
    assert analysis["decision_routes"]["proposal_review_route"] == "/forge/proposals/decision"
    assert (
        analysis["decision_routes"]["pack_review_decision_route"]
        == "/plugins/capabilities/packs/operator/review/decisions"
    )
    assert analysis["decision_routes"]["promotion_route_after_review"] == "/plugins/enable"
    assert analysis["requirements"]["operator_review_before_promotion_required"] is True
    assert analysis["requirements"]["review_decision_remains_separate_governed_action"] is True
    assert analysis["requirements"]["pack_review_receipt_required_before_pack_promotion"] is True
    assert analysis["governance"]["read_only"] is True
    assert analysis["governance"]["operator_facing"] is True
    assert analysis["governance"]["does_not_approve_proposals"] is True
    assert analysis["governance"]["does_not_promote_capabilities"] is True
    assert analysis["governance"]["promotion_authority"] is False
    assert analysis["next_smallest_truthful_gap"] == "stage17_capability_pack_review_decisions"

    pack = analysis["packs"][0]
    assert pack["pack_id"] == "ops.deploy"
    assert pack["status"] == "ready_for_operator_review"
    assert pack["operator_review_ready"] is True
    assert pack["decision_required"] is True
    assert pack["decision_kind"] == "staged_pack_promotion_review"
    assert pack["blockers"] == []
    assert pack["operator_review_rule_declared"] is True
    assert pack["operator_review_governance_declared"] is True
    assert pack["quality_evidence_ready"] is True
    assert pack["proposal_lineage_ready"] is True
    assert pack["validation_receipts_ready"] is True
    assert pack["promotion_receipts_ready"] is True
    assert pack["review_items_sample"][0]["capability"] == "generated.deploy"
    assert pack["review_items_sample"][0]["proposal_id"] == "plugin_proposal_generated_deploy"
    assert pack["failing_capabilities_sample"] == []


def test_capability_pack_operator_review_blocks_missing_review_contracts_and_evidence() -> None:
    analysis = analyze_capability_pack_operator_review(
        [
            {
                "capability": "generated.legacy",
                "version": "0.1.0",
                "source": "generated",
                "status": "staged",
                "risk_tier": "normal",
                "quality": {"tests": [], "docs": []},
                "metadata": {
                    "pack_id": "legacy.generated",
                    "pack_version": "0.0.0-migration",
                    "pack_name": "Legacy Generated Pack",
                    "promotion_rules": ["quality_standards_before_promotion"],
                    "pack_governance": {"scope": "build_dev"},
                },
            }
        ]
    )

    assert analysis["status"] == "blocked"
    assert analysis["ready_pack_count"] == 0
    assert analysis["decision_required_pack_count"] == 0
    assert analysis["review_queue_count"] == 0
    assert analysis["next_smallest_truthful_gap"] == "stage17_capability_pack_operator_review_contracts"

    pack = analysis["packs"][0]
    assert pack["operator_review_ready"] is False
    assert pack["decision_required"] is False
    assert pack["operator_review_rule_declared"] is False
    assert pack["operator_review_governance_declared"] is False
    assert pack["quality_evidence_ready"] is False
    assert pack["proposal_lineage_ready"] is False
    assert pack["validation_receipts_ready"] is False
    assert pack["blockers"] == [
        "operator_review_rule_missing",
        "operator_review_governance_missing",
        "tests_missing",
        "docs_missing",
        "validation_receipt_missing",
        "proposal_lineage_missing",
    ]
    assert pack["failing_capabilities_sample"][0]["gaps"] == pack["blockers"]
