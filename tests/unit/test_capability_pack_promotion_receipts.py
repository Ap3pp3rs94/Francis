from __future__ import annotations

from francis.economy.markets.capability_pack_promotion_receipts import (
    analyze_capability_pack_promotion_receipts,
)


def test_capability_pack_promotion_receipts_pass_for_existing_promoted_receipt() -> None:
    analysis = analyze_capability_pack_promotion_receipts(
        [
            {
                "capability": "generated.deploy",
                "version": "0.1.0",
                "source": "generated",
                "status": "promoted",
                "promotion_receipt_id": "plugin_promotion_generated_deploy",
                "metadata": {
                    "pack_id": "ops.deploy",
                    "pack_version": "1.0.0",
                    "pack_name": "Ops Deploy Pack",
                    "promotion_receipt_path": "data/artifacts/plugins/promotions/plugin_promotion_generated_deploy.json",
                },
            }
        ],
        available_receipt_ids={"plugin_promotion_generated_deploy"},
        available_receipt_paths={"data/artifacts/plugins/promotions/plugin_promotion_generated_deploy.json"},
    )

    assert analysis["stage"] == "Stage 17 / Capability Economy"
    assert analysis["status"] == "ready"
    assert analysis["pack_total"] == 1
    assert analysis["ready_pack_count"] == 1
    assert analysis["available_promotion_receipt_count"] == 1
    assert analysis["requirements"]["promotion_receipts_required_for_promoted"] is True
    assert analysis["requirements"]["promotion_receipt_bodies_not_read"] is True
    assert analysis["requirements"]["promotion_decisions_remain_separate_governed_actions"] is True
    assert analysis["governance"]["read_only"] is True
    assert analysis["governance"]["does_not_read_receipt_bodies"] is True
    assert analysis["governance"]["does_not_promote_capabilities"] is True
    assert analysis["governance"]["promotion_authority"] is False
    assert analysis["next_smallest_truthful_gap"] == "stage17_capability_pack_operator_surface"

    pack = analysis["packs"][0]
    assert pack["pack_id"] == "ops.deploy"
    assert pack["ready"] is True
    assert pack["blockers"] == []
    assert pack["requires_promotion_receipt_count"] == 1
    assert pack["promotion_receipt_present_count"] == 1
    assert pack["promotion_receipt_missing_count"] == 0
    assert pack["promotion_receipt_not_found_count"] == 0
    assert pack["promotion_receipt_invalid_count"] == 0
    assert pack["promotion_receipt_ids"] == ["plugin_promotion_generated_deploy"]
    assert pack["failing_capabilities_sample"] == []


def test_capability_pack_promotion_receipts_block_missing_invalid_and_unknown_receipts() -> None:
    analysis = analyze_capability_pack_promotion_receipts(
        [
            {
                "capability": "generated.empty",
                "version": "0.1.0",
                "source": "generated",
                "status": "promoted",
                "metadata": {
                    "pack_id": "legacy.generated",
                    "pack_version": "0.0.0-migration",
                    "pack_name": "Legacy Generated Pack",
                },
            },
            {
                "capability": "generated.bad",
                "version": "0.1.0",
                "source": "generated",
                "status": "promoted",
                "metadata": {
                    "pack_id": "legacy.generated",
                    "pack_version": "0.0.0-migration",
                    "pack_name": "Legacy Generated Pack",
                    "promotion_receipt_id": "../bad",
                    "promotion_receipt_path": "../outside.json",
                },
            },
            {
                "capability": "generated.unknown",
                "version": "0.1.0",
                "source": "generated",
                "status": "promoted",
                "metadata": {
                    "pack_id": "legacy.generated",
                    "pack_version": "0.0.0-migration",
                    "pack_name": "Legacy Generated Pack",
                    "promotion_receipt_id": "plugin_promotion_missing",
                    "promotion_receipt_path": "data/artifacts/plugins/promotions/plugin_promotion_missing.json",
                },
            },
        ],
        available_receipt_ids={"plugin_promotion_existing"},
        available_receipt_paths={"data/artifacts/plugins/promotions/plugin_promotion_existing.json"},
    )

    assert analysis["status"] == "blocked"
    assert analysis["blocked_pack_count"] == 1
    assert analysis["next_smallest_truthful_gap"] == "stage17_capability_pack_promotion_receipts"

    pack = analysis["packs"][0]
    assert pack["ready"] is False
    assert pack["blockers"] == [
        "promotion_receipt_id_missing",
        "promotion_receipt_id_invalid",
        "promotion_receipt_path_invalid",
        "promotion_receipt_not_found",
    ]
    assert pack["requires_promotion_receipt_count"] == 3
    assert pack["promotion_receipt_present_count"] == 0
    assert pack["promotion_receipt_missing_count"] == 1
    assert pack["promotion_receipt_invalid_count"] == 1
    assert pack["promotion_receipt_not_found_count"] == 1

    failing = {item["capability"]: item for item in pack["failing_capabilities_sample"]}
    assert failing["generated.empty"]["gaps"] == ["promotion_receipt_id_missing"]
    assert failing["generated.bad"]["gaps"] == [
        "promotion_receipt_id_invalid",
        "promotion_receipt_path_invalid",
    ]
    assert failing["generated.unknown"]["gaps"] == ["promotion_receipt_not_found"]
