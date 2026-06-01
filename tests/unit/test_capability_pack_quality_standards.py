from __future__ import annotations

from francis.economy.markets.capability_pack_quality_standards import analyze_capability_pack_quality_standards


def test_capability_pack_quality_standards_pass_for_tested_documented_receipted_pack() -> None:
    standards = analyze_capability_pack_quality_standards(
        [
            {
                "capability": "generated.deploy",
                "version": "0.1.0",
                "source": "generated",
                "status": "staged",
                "risk_tier": "normal",
                "proposal_id": "proposal_generated_deploy",
                "quality": {"tests": ["tests/test_deploy.py"], "docs": ["README.md"]},
                "metadata": {
                    "validation_receipt_id": "validation_generated_deploy",
                    "known_limits": ["local_only"],
                    "pack_id": "ops.deploy",
                    "pack_version": "1.0.0",
                    "pack_name": "Ops Deploy Pack",
                },
            }
        ]
    )

    assert standards["stage"] == "Stage 17 / Capability Economy"
    assert standards["status"] == "ready"
    assert standards["pack_total"] == 1
    assert standards["ready_pack_count"] == 1
    assert standards["governance"]["read_only"] is True
    assert standards["governance"]["does_not_promote_capabilities"] is True
    assert standards["next_smallest_truthful_gap"] == "stage17_capability_pack_promotion_rules"

    pack = standards["packs"][0]
    assert pack["pack_id"] == "ops.deploy"
    assert pack["ready"] is True
    assert pack["blockers"] == []
    assert pack["tested_count"] == 1
    assert pack["documented_count"] == 1
    assert pack["validation_receipt_count"] == 1
    assert pack["proposal_lineage_count"] == 1
    assert pack["known_limits_count"] == 1
    assert pack["failing_capabilities_sample"] == []


def test_capability_pack_quality_standards_block_missing_evidence() -> None:
    standards = analyze_capability_pack_quality_standards(
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
                },
            }
        ]
    )

    assert standards["status"] == "blocked"
    assert standards["blocked_pack_count"] == 1
    assert standards["next_smallest_truthful_gap"] == "stage17_capability_pack_quality_tests"

    pack = standards["packs"][0]
    assert pack["ready"] is False
    assert pack["blockers"] == [
        "tests_missing",
        "docs_missing",
        "validation_receipt_missing",
        "proposal_id_missing",
    ]
    assert pack["tested_count"] == 0
    assert pack["documented_count"] == 0
    assert pack["validation_receipt_count"] == 0
    assert pack["proposal_lineage_count"] == 0
    assert pack["failing_capabilities_sample"][0]["gaps"] == pack["blockers"]
