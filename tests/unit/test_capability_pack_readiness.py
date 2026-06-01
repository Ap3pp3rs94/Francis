from __future__ import annotations

from francis.economy.markets.capability_pack_readiness import analyze_capability_pack_readiness


def test_capability_pack_readiness_projects_stage17_pack_gates() -> None:
    analysis = analyze_capability_pack_readiness(
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
                    "promotion_rules": ["validated_before_promotion"],
                    "pack_governance": {
                        "risk_tier": "critical",
                        "approval_required": True,
                        "scope": "build_dev",
                    },
                },
            },
            {
                "capability": "generated.rollback",
                "version": "0.1.0",
                "source": "generated",
                "status": "staged",
                "risk_tier": "critical",
                "proposal_id": "proposal_generated_rollback",
                "quality": {"tests": ["tests/test_rollback.py"], "docs": ["docs/rollback.md"]},
                "metadata": {
                    "validation_receipt_id": "validation_generated_rollback",
                    "pack_id": "ops.deploy",
                    "pack_version": "1.0.0",
                    "pack_name": "Ops Deploy Pack",
                    "promotion_rules": ["validated_before_promotion"],
                    "pack_governance": {
                        "risk_tier": "critical",
                        "approval_required": True,
                        "scope": "build_dev",
                    },
                },
            },
        ]
    )

    assert analysis["stage"] == "Stage 17 / Capability Economy"
    assert analysis["status"] == "ready"
    assert analysis["pack_total"] == 1
    assert analysis["ready_pack_count"] == 1
    assert analysis["unpacked_entry_count"] == 0
    assert analysis["next_smallest_truthful_gap"] == "stage17_capability_pack_operator_surface"

    pack = analysis["packs"][0]
    assert pack["pack_id"] == "ops.deploy"
    assert pack["pack_version"] == "1.0.0"
    assert pack["pack_name"] == "Ops Deploy Pack"
    assert pack["ready"] is True
    assert pack["versioned_pack"] is True
    assert pack["promotion_rules_ready"] is True
    assert pack["quality_standards_ready"] is True
    assert pack["governance_travels"] is True
    assert pack["reusable_asset"] is True
    assert [item["capability"] for item in pack["capabilities"]] == ["generated.deploy", "generated.rollback"]


def test_capability_pack_readiness_blocks_unpackaged_and_ungoverned_capabilities() -> None:
    analysis = analyze_capability_pack_readiness(
        [
            {
                "capability": "generated.no_pack",
                "version": "0.1.0",
                "source": "generated",
                "status": "staged",
                "risk_tier": "normal",
                "proposal_id": "proposal_no_pack",
                "quality": {"tests": ["tests/test_no_pack.py"], "docs": ["docs/no-pack.md"]},
                "metadata": {"validation_receipt_id": "validation_no_pack"},
            },
            {
                "capability": "generated.ungoverned",
                "version": "0.1.0",
                "source": "generated",
                "status": "staged",
                "risk_tier": "normal",
                "proposal_id": "proposal_ungoverned",
                "quality": {"tests": [], "docs": ["docs/ungoverned.md"]},
                "metadata": {
                    "pack_id": "ops.partial",
                    "pack_version": "1.0.0",
                    "validation_receipt_id": "validation_ungoverned",
                },
            },
        ]
    )

    assert analysis["status"] == "blocked"
    assert analysis["unpacked_entry_count"] == 1
    assert analysis["unpacked_capabilities_truncated"] is False
    assert analysis["pack_total"] == 1
    assert analysis["blocked_pack_count"] == 1
    assert analysis["unpacked_capabilities"][0]["capability"] == "generated.no_pack"
    assert analysis["next_smallest_truthful_gap"] == "stage17_versioned_capability_pack_metadata"

    pack = analysis["packs"][0]
    assert pack["pack_id"] == "ops.partial"
    assert pack["ready"] is False
    assert pack["blockers"] == ["promotion_rules_missing", "pack_governance_missing", "tests_missing"]
    assert pack["governance_travels"] is False
    assert pack["quality_standards_ready"] is False


def test_capability_pack_readiness_bounds_unpacked_capability_sample() -> None:
    analysis = analyze_capability_pack_readiness(
        {
            "capability": f"generated.unpacked_{index}",
            "version": "0.1.0",
            "source": "generated",
            "status": "staged",
            "risk_tier": "normal",
        }
        for index in range(75)
    )

    assert analysis["status"] == "blocked"
    assert analysis["unpacked_entry_count"] == 75
    assert len(analysis["unpacked_capabilities"]) == 50
    assert analysis["unpacked_capabilities_truncated"] is True
