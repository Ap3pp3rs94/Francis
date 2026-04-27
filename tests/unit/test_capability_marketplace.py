from __future__ import annotations

from francis.economy.markets import CapabilityListing, CapabilityMarketplace


def test_capability_marketplace_projects_lifecycle_and_provenance_catalog() -> None:
    marketplace = CapabilityMarketplace()
    marketplace.add_listing(
        CapabilityListing(
            capability="generated.deploy",
            price=0.0,
            version="0.1.0",
            status="staged",
            risk_tier="critical",
            source="forge",
            proposal_id="proposal_generated_deploy",
            tests=("tests/test_deploy.py",),
            docs=("docs/deploy.md",),
            metadata={"mission_id": "msn_repeat_deploy"},
        )
    )
    marketplace.add_listing(
        CapabilityListing(
            capability="builtin.lookup",
            price=0.0,
            version="1.0.0",
            status="promoted",
            risk_tier="readonly",
            source="builtin",
            promotion_receipt_id="receipt_builtin_lookup",
            docs=("docs/lookup.md",),
        )
    )

    catalog = marketplace.catalog()

    assert [entry["capability"] for entry in catalog] == ["builtin.lookup", "generated.deploy"]
    assert catalog[0]["promotion_receipt_id"] == "receipt_builtin_lookup"
    assert catalog[1]["status"] == "staged"
    assert catalog[1]["risk_tier"] == "critical"
    assert catalog[1]["source"] == "forge"
    assert catalog[1]["proposal_id"] == "proposal_generated_deploy"
    assert catalog[1]["quality"] == {"tests": ["tests/test_deploy.py"], "docs": ["docs/deploy.md"]}
    assert catalog[1]["metadata"] == {"mission_id": "msn_repeat_deploy"}

    assert [entry["capability"] for entry in marketplace.catalog(status="staged")] == ["generated.deploy"]
    assert [entry["capability"] for entry in marketplace.catalog(risk_tier="readonly")] == ["builtin.lookup"]
    assert [entry["capability"] for entry in marketplace.catalog(source="forge")] == ["generated.deploy"]

    assert marketplace.summary() == {
        "total": 2,
        "status_counts": {"promoted": 1, "staged": 1},
        "risk_tier_counts": {"critical": 1, "readonly": 1},
        "source_counts": {"builtin": 1, "forge": 1},
        "tested_count": 1,
        "documented_count": 2,
    }
