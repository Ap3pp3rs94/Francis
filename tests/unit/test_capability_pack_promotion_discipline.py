from __future__ import annotations

from francis.economy.markets.capability_pack_promotion_discipline import (
    analyze_capability_pack_promotion_discipline,
)


def test_capability_pack_promotion_discipline_passes_for_reviewed_quality_pack() -> None:
    analysis = analyze_capability_pack_promotion_discipline(
        [
            {
                "capability": "generated.deploy",
                "version": "0.1.0",
                "source": "generated",
                "status": "staged",
                "proposal_id": "plugin_proposal_deploy",
                "metadata": {
                    "pack_id": "ops.deploy",
                    "pack_version": "1.0.0",
                    "pack_name": "Ops Deploy Pack",
                    "validation_receipt_id": "plugin_validation_deploy",
                    "promotion_rules": [
                        "metadata_receipt_before_promotion",
                        "quality_standards_before_promotion",
                        "operator_review_before_promotion",
                    ],
                    "pack_governance": {"scope": "build_dev", "operator_review_required": True},
                },
                "quality": {"tests": ["tests/test_deploy.py"], "docs": ["docs/deploy.md"]},
            }
        ],
        available_proposal_ids={"plugin_proposal_deploy"},
        available_validation_receipt_ids={"plugin_validation_deploy"},
        operator_review_decisions=[
            {
                "receipt_id": "capability_pack_operator_review_1_ops_deploy",
                "status": "approved",
                "pack_id": "ops.deploy",
                "pack_version": "1.0.0",
                "capability_ids": ["generated.deploy"],
            }
        ],
    )

    assert analysis["stage"] == "Stage 17 / Capability Economy"
    assert analysis["status"] == "ready"
    assert analysis["ready_pack_count"] == 1
    assert analysis["blocked_pack_count"] == 0
    assert analysis["requirements"]["mixed_pack_lifecycle_requires_explicit_discipline_readback"] is True
    assert analysis["requirements"]["promotion_discipline_is_read_only"] is True
    assert analysis["governance"]["read_only"] is True
    assert analysis["governance"]["does_not_promote_capabilities"] is True
    assert analysis["governance"]["promotion_authority"] is False
    assert analysis["next_smallest_truthful_gap"] == "stage17_capability_library_operator_surface"

    pack = analysis["packs"][0]
    assert pack["pack_id"] == "ops.deploy"
    assert pack["ready"] is True
    assert pack["blockers"] == []
    assert pack["operator_review_approved"] is True
    assert pack["operator_review_approved_capability_count"] == 1
    assert pack["operator_review_missing_capability_count"] == 0
    assert pack["operator_review_missing_capabilities_sample"] == []
    assert pack["promotion_rules_ready"] is True
    assert pack["quality_evidence_ready"] is True
    assert pack["validation_receipts_ready"] is True
    assert pack["proposal_lineage_ready"] is True
    assert pack["lifecycle_mixed"] is False
    assert pack["failing_capabilities_sample"] == []


def test_capability_pack_promotion_discipline_blocks_partial_review_coverage() -> None:
    entries = [
        {
            "capability": "generated.deploy",
            "version": "0.1.0",
            "source": "generated",
            "status": "staged",
            "proposal_id": "plugin_proposal_deploy",
            "metadata": {
                "pack_id": "ops.deploy",
                "pack_version": "1.0.0",
                "pack_name": "Ops Deploy Pack",
                "validation_receipt_id": "plugin_validation_deploy",
                "promotion_rules": [
                    "metadata_receipt_before_promotion",
                    "quality_standards_before_promotion",
                    "operator_review_before_promotion",
                ],
                "pack_governance": {"scope": "build_dev", "operator_review_required": True},
            },
            "quality": {"tests": ["tests/test_deploy.py"], "docs": ["docs/deploy.md"]},
        },
        {
            "capability": "generated.rollback",
            "version": "0.1.0",
            "source": "generated",
            "status": "staged",
            "proposal_id": "plugin_proposal_rollback",
            "metadata": {
                "pack_id": "ops.deploy",
                "pack_version": "1.0.0",
                "pack_name": "Ops Deploy Pack",
                "validation_receipt_id": "plugin_validation_rollback",
                "promotion_rules": [
                    "metadata_receipt_before_promotion",
                    "quality_standards_before_promotion",
                    "operator_review_before_promotion",
                ],
                "pack_governance": {"scope": "build_dev", "operator_review_required": True},
            },
            "quality": {"tests": ["tests/test_rollback.py"], "docs": ["docs/rollback.md"]},
        },
    ]

    analysis = analyze_capability_pack_promotion_discipline(
        entries,
        available_proposal_ids={"plugin_proposal_deploy", "plugin_proposal_rollback"},
        available_validation_receipt_ids={"plugin_validation_deploy", "plugin_validation_rollback"},
        operator_review_decisions=[
            {
                "receipt_id": "capability_pack_operator_review_1_ops_deploy",
                "status": "approved",
                "pack_id": "ops.deploy",
                "pack_version": "1.0.0",
                "capability_ids": ["generated.deploy"],
            }
        ],
    )

    assert analysis["status"] == "blocked"
    assert analysis["ready_pack_count"] == 0
    assert analysis["blocked_pack_count"] == 1
    assert analysis["approved_pack_operator_review_count"] == 0
    assert analysis["next_smallest_truthful_gap"] == "stage17_capability_pack_review_decisions"

    pack = analysis["packs"][0]
    assert pack["operator_review_approved"] is False
    assert pack["operator_review_approved_capability_count"] == 1
    assert pack["operator_review_missing_capability_count"] == 1
    assert pack["operator_review_missing_capabilities_sample"] == ["generated.rollback"]
    assert "operator_review_decision_missing" in pack["blockers"]


def test_capability_pack_promotion_discipline_ignores_disabled_generated_packs() -> None:
    analysis = analyze_capability_pack_promotion_discipline(
        [
            {
                "capability": "generated.disabled",
                "version": "0.1.0",
                "source": "generated",
                "status": "disabled",
                "metadata": {
                    "pack_id": "legacy.generated.disabled",
                    "pack_version": "0.0.0-migration",
                    "pack_name": "Legacy Generated Disabled Pack",
                },
                "quality": {"tests": [], "docs": []},
            }
        ]
    )

    assert analysis["status"] == "empty"
    assert analysis["total_entries"] == 1
    assert analysis["active_entry_count"] == 0
    assert analysis["inactive_entry_count"] == 1
    assert analysis["pack_total"] == 0
    assert analysis["blocked_pack_count"] == 0
    assert analysis["packs"] == []


def test_capability_pack_promotion_discipline_blocks_weak_pack_promotion_posture() -> None:
    analysis = analyze_capability_pack_promotion_discipline(
        [
            {
                "capability": "generated.deploy",
                "version": "0.1.0",
                "source": "generated",
                "status": "staged",
                "proposal_id": "plugin_proposal_missing",
                "metadata": {
                    "pack_id": "ops.weak",
                    "pack_version": "1.0.0",
                    "pack_name": "Weak Ops Pack",
                    "validation_receipt_id": "plugin_validation_missing",
                    "promotion_rules": ["metadata_receipt_before_promotion"],
                    "pack_governance": {"scope": "build_dev"},
                },
                "quality": {"tests": ["tests/test_deploy.py"], "docs": []},
            },
            {
                "capability": "generated.rollback",
                "version": "0.1.0",
                "source": "generated",
                "status": "promoted",
                "promotion_receipt_id": "plugin_promotion_missing",
                "metadata": {
                    "pack_id": "ops.weak",
                    "pack_version": "1.0.0",
                    "pack_name": "Weak Ops Pack",
                    "validation_receipt_id": "plugin_validation_rollback",
                    "promotion_rules": ["metadata_receipt_before_promotion"],
                    "pack_governance": {"scope": "build_dev"},
                },
                "quality": {"tests": ["tests/test_rollback.py"], "docs": ["docs/rollback.md"]},
            },
        ],
        available_validation_receipt_ids={"plugin_validation_rollback"},
    )

    assert analysis["status"] == "blocked"
    assert analysis["ready_pack_count"] == 0
    assert analysis["blocked_pack_count"] == 1
    assert analysis["next_smallest_truthful_gap"] == "stage17_capability_pack_quality_docs"

    pack = analysis["packs"][0]
    assert pack["ready"] is False
    assert pack["lifecycle_mixed"] is True
    assert pack["blockers"] == [
        "docs_missing",
        "validation_receipt_not_found",
        "proposal_not_found",
        "promotion_receipt_not_found",
        "operator_review_rule_missing",
        "operator_review_governance_missing",
        "operator_review_decision_missing",
        "mixed_staged_and_promoted_pack",
    ]

    failing = {item["capability"]: item for item in pack["failing_capabilities_sample"]}
    assert failing["generated.deploy"]["gaps"] == [
        "docs_missing",
        "validation_receipt_not_found",
        "proposal_not_found",
    ]
    assert failing["generated.rollback"]["gaps"] == ["promotion_receipt_not_found"]
