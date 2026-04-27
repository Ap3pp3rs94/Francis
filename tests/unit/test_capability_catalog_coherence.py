from __future__ import annotations

from francis.economy.markets.capability_catalog_coherence import analyze_capability_catalog_coherence


def test_capability_catalog_coherence_flags_duplicates_lineage_and_quality_gaps() -> None:
    analysis = analyze_capability_catalog_coherence(
        [
            {
                "capability": "generated.deploy",
                "version": "0.1.0",
                "source": "forge",
                "status": "staged",
                "risk_tier": "critical",
                "proposal_id": "proposal_shared",
                "quality": {"tests": ["tests/test_deploy.py"], "docs": ["docs/deploy.md"]},
            },
            {
                "capability": "generated.deploy",
                "version": "0.2.0",
                "source": "forge",
                "status": "staged",
                "risk_tier": "critical",
                "proposal_id": "proposal_shared",
                "quality": {"tests": [], "docs": ["docs/deploy-v2.md"]},
            },
            {
                "capability": "generated.rollback",
                "version": "0.1.0",
                "source": "forge",
                "status": "staged",
                "risk_tier": "normal",
                "proposal_id": "proposal_shared",
                "quality": {"tests": ["tests/test_rollback.py"], "docs": ["docs/rollback.md"]},
            },
            {
                "capability": "builtin.lookup",
                "version": "1.0.0",
                "source": "builtin",
                "status": "promoted",
                "risk_tier": "readonly",
                "quality": {"tests": ["tests/test_lookup.py"], "docs": []},
            },
            {
                "capability": "generated.no_lineage",
                "version": "0.1.0",
                "source": "forge",
                "status": "staged",
                "risk_tier": "normal",
                "quality": {"tests": ["tests/test_no_lineage.py"], "docs": ["docs/no_lineage.md"]},
            },
        ]
    )

    assert analysis["total"] == 5
    assert analysis["duplicate_capabilities"] == [
        {
            "capability": "generated.deploy",
            "entries": [
                {
                    "capability": "generated.deploy",
                    "version": "0.1.0",
                    "source": "forge",
                    "status": "staged",
                    "risk_tier": "critical",
                },
                {
                    "capability": "generated.deploy",
                    "version": "0.2.0",
                    "source": "forge",
                    "status": "staged",
                    "risk_tier": "critical",
                },
            ],
        }
    ]
    assert analysis["duplicate_proposals"] == [
        {
            "proposal_id": "proposal_shared",
            "capabilities": ["generated.deploy", "generated.rollback"],
        }
    ]
    assert analysis["lineage_gaps"] == [
        {
            "capability": "builtin.lookup",
            "version": "1.0.0",
            "source": "builtin",
            "status": "promoted",
            "risk_tier": "readonly",
            "missing": ["promotion_receipt_id"],
        },
        {
            "capability": "generated.no_lineage",
            "version": "0.1.0",
            "source": "forge",
            "status": "staged",
            "risk_tier": "normal",
            "missing": ["proposal_id"],
        },
    ]
    assert analysis["quality_gaps"] == [
        {
            "capability": "generated.deploy",
            "version": "0.2.0",
            "source": "forge",
            "status": "staged",
            "risk_tier": "critical",
            "missing": ["tests"],
        },
        {
            "capability": "builtin.lookup",
            "version": "1.0.0",
            "source": "builtin",
            "status": "promoted",
            "risk_tier": "readonly",
            "missing": ["docs"],
        },
    ]


def test_capability_catalog_coherence_ignores_blank_capability_entries() -> None:
    analysis = analyze_capability_catalog_coherence([{"capability": ""}, {"version": "1.0.0"}])

    assert analysis == {
        "total": 0,
        "duplicate_capabilities": [],
        "duplicate_proposals": [],
        "lineage_gaps": [],
        "quality_gaps": [],
    }
