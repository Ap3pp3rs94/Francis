from __future__ import annotations

from francis.economy.markets import capability_listings_from_plugin_catalog, marketplace_from_plugin_catalog


def test_plugin_registry_catalog_projects_to_capability_marketplace() -> None:
    catalog = {
        "plugins": [
            {
                "plugin_id": "generated.deploy",
                "name": "Generated Deploy",
                "version": "0.1.0",
                "origin": "generated",
                "risk_class": "critical",
                "capabilities": ["generated", "deploy"],
                "metadata": {
                    "promotion_status": "staged",
                    "proposal_id": "proposal_generated_deploy",
                    "proposal_path": "data/artifacts/plugins/proposals/proposal_generated_deploy.json",
                    "proposal_evidence": ["mission.deploy.repeat"],
                    "risk_tier": "critical",
                    "tests": ["tests/test_deploy.py"],
                    "docs": ["docs/deploy.md"],
                    "validation_path": ["python -m pytest tests/test_deploy.py"],
                    "validation_receipt_id": "plugin_validation_generated_deploy",
                    "validation_receipt_path": "data/artifacts/plugins/validations/plugin_validation_generated_deploy.json",
                    "known_limits": ["local-only"],
                },
            },
            {
                "plugin_id": "builtin.lookup",
                "name": "Builtin Lookup",
                "version": "1.0.0",
                "origin": "builtin",
                "risk_class": "readonly",
                "metadata": {
                    "promotion_status": "promoted",
                    "promotion_receipt_id": "receipt_builtin_lookup",
                    "promotion_receipt_path": "data/artifacts/plugins/promotions/receipt_builtin_lookup.json",
                    "docs": ["docs/lookup.md"],
                },
            },
            {"name": "missing id"},
        ]
    }

    listings = capability_listings_from_plugin_catalog(catalog)

    assert [listing.capability for listing in listings] == ["builtin.lookup", "generated.deploy"]
    assert listings[0].status == "promoted"
    assert listings[0].risk_tier == "readonly"
    assert listings[0].promotion_receipt_id == "receipt_builtin_lookup"
    assert listings[1].status == "staged"
    assert listings[1].risk_tier == "critical"
    assert listings[1].source == "generated"
    assert listings[1].proposal_id == "proposal_generated_deploy"
    assert listings[1].tests == ("tests/test_deploy.py",)
    assert listings[1].docs == ("docs/deploy.md",)
    assert listings[1].metadata["proposal_evidence"] == ["mission.deploy.repeat"]
    assert listings[1].metadata["pack_id"] == "legacy.generated.generated_deploy"
    assert listings[1].metadata["pack_version"] == "0.0.0-migration"
    assert listings[1].metadata["pack_metadata_source"] == "legacy_generated_projection"
    assert listings[1].metadata["validation_receipt_id"] == "plugin_validation_generated_deploy"
    assert (
        listings[1].metadata["validation_receipt_path"]
        == "data/artifacts/plugins/validations/plugin_validation_generated_deploy.json"
    )
    assert listings[1].metadata["plugin_name"] == "Generated Deploy"

    marketplace = marketplace_from_plugin_catalog(catalog)

    assert [entry["capability"] for entry in marketplace.catalog(status="staged")] == ["generated.deploy"]
    assert marketplace.summary() == {
        "total": 2,
        "status_counts": {"promoted": 1, "staged": 1},
        "risk_tier_counts": {"critical": 1, "readonly": 1},
        "source_counts": {"builtin": 1, "generated": 1},
        "tested_count": 1,
        "documented_count": 2,
    }


def test_plugin_registry_catalog_projects_legacy_source_kind_to_migration_pack_metadata() -> None:
    catalog = {
        "plugins": [
            {
                "id": "1771955744_opsplugin",
                "name": "Ops Plugin",
                "source_kind": "generated",
                "tags": ["generated"],
                "generated_dir": "plugins/generated/1771955744_opsplugin",
                "meta": {
                    "promotion_status": "staged",
                    "quality": {
                        "tests": ["tests/test_ops.py"],
                        "docs": ["README.md"],
                    },
                },
            }
        ]
    }

    listing = capability_listings_from_plugin_catalog(catalog)[0]

    assert listing.source == "generated"
    assert listing.tests == ("tests/test_ops.py",)
    assert listing.docs == ("README.md",)
    assert listing.metadata["pack_id"] == "legacy.generated.opsplugin"
    assert listing.metadata["pack_version"] == "0.0.0-migration"
    assert listing.metadata["pack_name"] == "Legacy Generated Opsplugin Pack"
    assert listing.metadata["pack_metadata_source"] == "legacy_generated_projection"
    assert (
        listing.metadata["pack_migration_reason"] == "legacy_generated_artifact_missing_explicit_stage17_pack_metadata"
    )
