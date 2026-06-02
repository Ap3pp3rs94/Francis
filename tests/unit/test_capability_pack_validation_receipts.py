from __future__ import annotations

from francis.economy.markets.capability_pack_validation_receipts import analyze_capability_pack_validation_receipts


def test_capability_pack_validation_receipts_pass_for_existing_generated_receipt() -> None:
    analysis = analyze_capability_pack_validation_receipts(
        [
            {
                "capability": "generated.deploy",
                "version": "0.1.0",
                "source": "generated",
                "status": "staged",
                "metadata": {
                    "pack_id": "ops.deploy",
                    "pack_version": "1.0.0",
                    "pack_name": "Ops Deploy Pack",
                    "validation_receipt_id": "plugin_validation_generated_deploy",
                    "validation_receipt_path": (
                        "data/artifacts/plugins/validations/plugin_validation_generated_deploy.json"
                    ),
                },
            }
        ],
        available_receipt_ids={"plugin_validation_generated_deploy"},
        available_receipt_paths={
            "data/artifacts/plugins/validations/plugin_validation_generated_deploy.json",
        },
    )

    assert analysis["stage"] == "Stage 17 / Capability Economy"
    assert analysis["status"] == "ready"
    assert analysis["pack_total"] == 1
    assert analysis["ready_pack_count"] == 1
    assert analysis["available_validation_receipt_count"] == 1
    assert analysis["requirements"]["validation_receipts_required_for_generated"] is True
    assert analysis["requirements"]["validation_receipt_bodies_not_read"] is True
    assert analysis["governance"]["read_only"] is True
    assert analysis["governance"]["does_not_read_receipt_bodies"] is True
    assert analysis["governance"]["does_not_write_receipts"] is True
    assert analysis["governance"]["does_not_promote_capabilities"] is True
    assert analysis["next_smallest_truthful_gap"] == "stage17_capability_pack_lineage"

    pack = analysis["packs"][0]
    assert pack["pack_id"] == "ops.deploy"
    assert pack["ready"] is True
    assert pack["blockers"] == []
    assert pack["requires_validation_receipt_count"] == 1
    assert pack["validation_receipt_present_count"] == 1
    assert pack["validation_receipt_missing_count"] == 0
    assert pack["validation_receipt_not_found_count"] == 0
    assert pack["validation_receipt_invalid_count"] == 0
    assert pack["validation_receipt_ids"] == ["plugin_validation_generated_deploy"]
    assert pack["failing_capabilities_sample"] == []


def test_capability_pack_validation_receipts_block_missing_invalid_and_unknown_receipts() -> None:
    analysis = analyze_capability_pack_validation_receipts(
        [
            {
                "capability": "generated.empty",
                "version": "0.1.0",
                "source": "generated",
                "status": "staged",
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
                "status": "staged",
                "metadata": {
                    "pack_id": "legacy.generated",
                    "pack_version": "0.0.0-migration",
                    "pack_name": "Legacy Generated Pack",
                    "validation_receipt_id": "../bad",
                    "validation_receipt_path": "../outside.json",
                },
            },
            {
                "capability": "generated.unknown",
                "version": "0.1.0",
                "source": "generated",
                "status": "staged",
                "metadata": {
                    "pack_id": "legacy.generated",
                    "pack_version": "0.0.0-migration",
                    "pack_name": "Legacy Generated Pack",
                    "validation_receipt_id": "plugin_validation_missing",
                    "validation_receipt_path": "data/artifacts/plugins/validations/plugin_validation_missing.json",
                },
            },
        ],
        available_receipt_ids={"plugin_validation_existing"},
        available_receipt_paths={"data/artifacts/plugins/validations/plugin_validation_existing.json"},
    )

    assert analysis["status"] == "blocked"
    assert analysis["blocked_pack_count"] == 1
    assert analysis["next_smallest_truthful_gap"] == "stage17_capability_pack_validation_receipts"

    pack = analysis["packs"][0]
    assert pack["ready"] is False
    assert pack["blockers"] == [
        "validation_receipt_missing",
        "validation_receipt_id_invalid",
        "validation_receipt_path_invalid",
        "validation_receipt_not_found",
    ]
    assert pack["requires_validation_receipt_count"] == 3
    assert pack["validation_receipt_present_count"] == 0
    assert pack["validation_receipt_missing_count"] == 1
    assert pack["validation_receipt_invalid_count"] == 1
    assert pack["validation_receipt_not_found_count"] == 1

    failing = {item["capability"]: item for item in pack["failing_capabilities_sample"]}
    assert failing["generated.empty"]["gaps"] == ["validation_receipt_missing"]
    assert failing["generated.bad"]["gaps"] == [
        "validation_receipt_id_invalid",
        "validation_receipt_path_invalid",
    ]
    assert failing["generated.unknown"]["gaps"] == ["validation_receipt_not_found"]
