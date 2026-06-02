from __future__ import annotations

from francis.economy.markets.capability_pack_lineage import analyze_capability_pack_lineage


def test_capability_pack_lineage_passes_for_existing_staged_proposal() -> None:
    analysis = analyze_capability_pack_lineage(
        [
            {
                "capability": "generated.deploy",
                "version": "0.1.0",
                "source": "generated",
                "status": "staged",
                "proposal_id": "plugin_proposal_generated_deploy",
                "metadata": {
                    "pack_id": "ops.deploy",
                    "pack_version": "1.0.0",
                    "pack_name": "Ops Deploy Pack",
                    "proposal_path": "data/artifacts/plugins/proposals/plugin_proposal_generated_deploy.json",
                },
            }
        ],
        available_proposal_ids={"plugin_proposal_generated_deploy"},
        available_proposal_paths={"data/artifacts/plugins/proposals/plugin_proposal_generated_deploy.json"},
    )

    assert analysis["stage"] == "Stage 17 / Capability Economy"
    assert analysis["status"] == "ready"
    assert analysis["pack_total"] == 1
    assert analysis["ready_pack_count"] == 1
    assert analysis["available_proposal_count"] == 1
    assert analysis["requirements"]["proposal_lineage_required_for_staged"] is True
    assert analysis["requirements"]["proposal_bodies_not_read"] is True
    assert analysis["requirements"]["operator_review_remains_separate_gate"] is True
    assert analysis["governance"]["read_only"] is True
    assert analysis["governance"]["does_not_read_proposal_bodies"] is True
    assert analysis["governance"]["does_not_approve_proposals"] is True
    assert analysis["governance"]["proposal_approval_authority"] is False
    assert analysis["next_smallest_truthful_gap"] == "stage17_capability_pack_promotion_receipts"

    pack = analysis["packs"][0]
    assert pack["pack_id"] == "ops.deploy"
    assert pack["ready"] is True
    assert pack["blockers"] == []
    assert pack["requires_proposal_lineage_count"] == 1
    assert pack["proposal_lineage_present_count"] == 1
    assert pack["proposal_id_missing_count"] == 0
    assert pack["proposal_not_found_count"] == 0
    assert pack["proposal_invalid_count"] == 0
    assert pack["proposal_ids"] == ["plugin_proposal_generated_deploy"]
    assert pack["failing_capabilities_sample"] == []


def test_capability_pack_lineage_blocks_missing_invalid_and_unknown_proposals() -> None:
    analysis = analyze_capability_pack_lineage(
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
                    "proposal_id": "../bad",
                    "proposal_path": "../outside.json",
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
                    "proposal_id": "plugin_proposal_missing",
                    "proposal_path": "data/artifacts/plugins/proposals/plugin_proposal_missing.json",
                },
            },
        ],
        available_proposal_ids={"plugin_proposal_existing"},
        available_proposal_paths={"data/artifacts/plugins/proposals/plugin_proposal_existing.json"},
    )

    assert analysis["status"] == "blocked"
    assert analysis["blocked_pack_count"] == 1
    assert analysis["next_smallest_truthful_gap"] == "stage17_capability_pack_lineage"

    pack = analysis["packs"][0]
    assert pack["ready"] is False
    assert pack["blockers"] == [
        "proposal_id_missing",
        "proposal_id_invalid",
        "proposal_path_invalid",
        "proposal_not_found",
    ]
    assert pack["requires_proposal_lineage_count"] == 3
    assert pack["proposal_lineage_present_count"] == 0
    assert pack["proposal_id_missing_count"] == 1
    assert pack["proposal_invalid_count"] == 1
    assert pack["proposal_not_found_count"] == 1

    failing = {item["capability"]: item for item in pack["failing_capabilities_sample"]}
    assert failing["generated.empty"]["gaps"] == ["proposal_id_missing"]
    assert failing["generated.bad"]["gaps"] == [
        "proposal_id_invalid",
        "proposal_path_invalid",
    ]
    assert failing["generated.unknown"]["gaps"] == ["proposal_not_found"]
