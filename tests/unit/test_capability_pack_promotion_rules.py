from __future__ import annotations

from francis.economy.markets.capability_pack_promotion_rules import (
    analyze_capability_pack_promotion_rule_remediation,
    analyze_capability_pack_promotion_rules,
)


def test_capability_pack_promotion_rules_pass_for_governed_quality_pack() -> None:
    analysis = analyze_capability_pack_promotion_rules(
        [
            {
                "capability": "generated.deploy",
                "version": "0.1.0",
                "source": "generated",
                "status": "staged",
                "risk_tier": "critical",
                "proposal_id": "proposal_generated_deploy",
                "quality": {"tests": ["tests/test_deploy.py"], "docs": ["docs/deploy.md"]},
                "metadata": {
                    "validation_receipt_id": "validation_generated_deploy",
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
                        "approval_required": True,
                        "scope": "build_dev",
                    },
                },
            }
        ]
    )

    assert analysis["stage"] == "Stage 17 / Capability Economy"
    assert analysis["status"] == "ready"
    assert analysis["pack_total"] == 1
    assert analysis["ready_pack_count"] == 1
    assert analysis["requirements"]["explicit_promotion_rules"] is True
    assert analysis["governance"]["read_only"] is True
    assert analysis["governance"]["does_not_promote_capabilities"] is True
    assert analysis["governance"]["promotion_authority"] is False
    assert analysis["next_smallest_truthful_gap"] == "stage17_capability_pack_operator_surface"

    pack = analysis["packs"][0]
    assert pack["pack_id"] == "ops.deploy"
    assert pack["ready"] is True
    assert pack["blockers"] == []
    assert pack["explicit_rules_ready"] is True
    assert pack["quality_standards_ready"] is True
    assert pack["governance_travels"] is True
    assert pack["operator_review_declared"] is True
    assert pack["promoted_capabilities_have_receipts"] is True
    assert pack["promotion_rules"] == [
        "metadata_receipt_before_promotion",
        "operator_review_before_promotion",
        "quality_standards_before_promotion",
    ]
    assert pack["failing_capabilities_sample"] == []


def test_capability_pack_promotion_rules_block_missing_rule_contracts() -> None:
    analysis = analyze_capability_pack_promotion_rules(
        [
            {
                "capability": "generated.legacy",
                "version": "0.1.0",
                "source": "generated",
                "status": "staged",
                "risk_tier": "normal",
                "quality": {"tests": [], "docs": []},
                "metadata": {
                    "pack_id": "legacy.generated.legacy",
                    "pack_version": "0.0.0-migration",
                    "pack_name": "Legacy Generated Legacy Pack",
                    "pack_metadata_source": "legacy_generated_projection",
                },
            }
        ]
    )

    assert analysis["status"] == "blocked"
    assert analysis["blocked_pack_count"] == 1
    assert analysis["next_smallest_truthful_gap"] == "stage17_capability_pack_metadata_receipts"

    pack = analysis["packs"][0]
    assert pack["ready"] is False
    assert pack["explicit_rules_ready"] is False
    assert pack["metadata_receipts_ready"] is False
    assert pack["quality_standards_ready"] is False
    assert pack["governance_travels"] is False
    assert pack["blockers"] == [
        "pack_metadata_receipt_missing",
        "promotion_rules_missing",
        "pack_governance_missing",
        "tests_missing",
        "docs_missing",
        "validation_receipt_missing",
        "proposal_id_missing",
    ]
    assert pack["failing_capabilities_sample"][0]["gaps"] == pack["blockers"]


def test_capability_pack_promotion_rule_remediation_projects_read_only_backlog() -> None:
    analysis = analyze_capability_pack_promotion_rule_remediation(
        [
            {
                "capability": "generated.partial",
                "version": "0.1.0",
                "source": "generated",
                "status": "staged",
                "risk_tier": "normal",
                "quality": {"tests": ["tests/test_partial.py"], "docs": []},
                "metadata": {
                    "pack_id": "legacy.generated.partial",
                    "pack_version": "0.0.0-migration",
                    "pack_name": "Legacy Generated Partial Pack",
                    "pack_metadata_source": "legacy_generated_projection",
                    "promotion_rules": ["metadata_receipt_before_promotion"],
                },
            }
        ]
    )

    assert analysis["stage"] == "Stage 17 / Capability Economy"
    assert analysis["status"] == "blocked"
    assert analysis["pack_total"] == 1
    assert analysis["remediation_pack_count"] == 1
    assert analysis["remediation_queue_count"] == 1
    assert analysis["missing_rule_pack_count"] == 1
    assert analysis["missing_governance_pack_count"] == 1
    assert analysis["missing_quality_pack_count"] == 1
    assert analysis["missing_receipt_pack_count"] == 1
    assert analysis["canonical_promotion_rules"] == [
        "metadata_receipt_before_promotion",
        "quality_standards_before_promotion",
        "operator_review_before_promotion",
    ]
    assert analysis["requirements"]["read_only_remediation_queue"] is True
    assert analysis["requirements"]["remediation_does_not_write_registry"] is True
    assert analysis["governance"]["read_only"] is True
    assert analysis["governance"]["operator_facing"] is True
    assert analysis["governance"]["does_not_write_receipts"] is True
    assert analysis["governance"]["does_not_mutate_registry"] is True
    assert analysis["governance"]["does_not_promote_capabilities"] is True
    assert analysis["governance"]["promotion_authority"] is False
    assert analysis["governance"]["memory_write"] is False
    assert analysis["next_smallest_truthful_gap"] == "stage17_capability_pack_promotion_rule_backlog_execution"

    item = analysis["remediation_queue"][0]
    assert item["pack_id"] == "legacy.generated.partial"
    assert item["first_action"] == "write_pack_metadata_receipt"
    assert item["missing_promotion_rules"] == [
        "quality_standards_before_promotion",
        "operator_review_before_promotion",
    ]
    assert item["missing_governance_fields"] == ["pack_governance", "operator_review_required"]
    assert item["missing_quality_evidence"] == ["docs", "validation_receipt", "forge_proposal"]
    assert item["missing_receipt_evidence"] == ["pack_metadata_receipt", "validation_receipt"]
    assert "canonical_promotion_rules_missing" in item["blockers"]
    assert item["failing_capabilities_sample"][0]["capability"] == "generated.partial"


def test_capability_pack_promotion_rule_remediation_is_empty_for_governed_pack() -> None:
    analysis = analyze_capability_pack_promotion_rule_remediation(
        [
            {
                "capability": "generated.ready",
                "version": "0.1.0",
                "source": "generated",
                "status": "staged",
                "risk_tier": "normal",
                "proposal_id": "proposal_generated_ready",
                "quality": {"tests": ["tests/test_ready.py"], "docs": ["docs/ready.md"]},
                "metadata": {
                    "validation_receipt_id": "validation_generated_ready",
                    "pack_id": "ops.ready",
                    "pack_version": "1.0.0",
                    "pack_name": "Ops Ready Pack",
                    "promotion_rules": [
                        "metadata_receipt_before_promotion",
                        "quality_standards_before_promotion",
                        "operator_review_before_promotion",
                    ],
                    "pack_governance": {"operator_review_required": True},
                },
            }
        ]
    )

    assert analysis["status"] == "ready"
    assert analysis["ready_pack_count"] == 1
    assert analysis["blocked_pack_count"] == 0
    assert analysis["remediation_pack_count"] == 0
    assert analysis["remediation_queue"] == []
    assert analysis["first_action"] == ""
    assert analysis["next_smallest_truthful_gap"] == "stage17_capability_pack_operator_surface"
