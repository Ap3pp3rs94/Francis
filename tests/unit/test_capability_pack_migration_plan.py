from __future__ import annotations

from francis.economy.markets.capability_pack_migration_plan import analyze_capability_pack_migration_plan


def test_capability_pack_migration_plan_projects_metadata_receipt_candidates() -> None:
    plan = analyze_capability_pack_migration_plan(
        [
            {
                "capability": "generated.ops_one",
                "version": "0.1.0",
                "source": "generated",
                "status": "staged",
                "risk_tier": "normal",
                "quality": {"tests": [], "docs": []},
                "metadata": {
                    "pack_id": "legacy.generated.ops",
                    "pack_version": "0.0.0-migration",
                    "pack_name": "Legacy Generated Ops Pack",
                    "pack_metadata_source": "legacy_generated_projection",
                },
            },
            {
                "capability": "generated.ops_two",
                "version": "0.1.0",
                "source": "generated",
                "status": "staged",
                "risk_tier": "normal",
                "quality": {"tests": [], "docs": []},
                "metadata": {
                    "pack_id": "legacy.generated.ops",
                    "pack_version": "0.0.0-migration",
                    "pack_name": "Legacy Generated Ops Pack",
                    "pack_metadata_source": "legacy_generated_projection",
                },
            },
        ]
    )

    assert plan["stage"] == "Stage 17 / Capability Economy"
    assert plan["status"] == "ready_for_metadata_receipt_review"
    assert plan["candidate_total"] == 1
    assert plan["write_route"] == "/plugins/capabilities/packs/metadata/receipts"
    assert plan["read_route"] == "/plugins/capabilities/packs/metadata/receipts"
    assert plan["governance"]["read_only"] is True
    assert plan["governance"]["does_not_write_receipts"] is True
    assert plan["governance"]["does_not_mutate_registry"] is True
    assert plan["next_smallest_truthful_gap"] == "stage17_capability_pack_metadata_receipt_operator_review"

    candidate = plan["candidates"][0]
    assert candidate["pack_id"] == "legacy.generated.ops"
    assert candidate["pack_version"] == "0.0.0-migration"
    assert candidate["capability_count"] == 2
    assert candidate["capability_ids_sample"] == ["generated.ops_one", "generated.ops_two"]
    assert candidate["requires_explicit_capability_id_selection"] is True
    assert candidate["suggested_pack_governance"]["promotion_authority"] is False
    assert candidate["suggested_pack_governance"]["execution_authority"] is False
    assert "metadata_receipt_before_promotion" in candidate["suggested_promotion_rules"]


def test_capability_pack_migration_plan_has_no_candidates_after_metadata_receipt() -> None:
    plan = analyze_capability_pack_migration_plan(
        [
            {
                "capability": "generated.receipted",
                "version": "0.1.0",
                "source": "generated",
                "status": "staged",
                "risk_tier": "normal",
                "proposal_id": "proposal_receipted",
                "quality": {"tests": ["tests/test_receipted.py"], "docs": ["README.md"]},
                "metadata": {
                    "validation_receipt_id": "validation_receipted",
                    "pack_id": "ops.receipted",
                    "pack_version": "1.0.0",
                    "pack_name": "Ops Receipted Pack",
                    "pack_metadata_source": "metadata_receipt",
                    "pack_metadata_receipt_id": "capability_pack_metadata_receipted",
                    "promotion_rules": ["metadata_receipt_before_promotion"],
                    "pack_governance": {"scope": "build_dev"},
                },
            },
        ]
    )

    assert plan["candidate_total"] == 0
    assert plan["candidates"] == []
    assert plan["governance"]["read_only"] is True
