from __future__ import annotations

from francis.forge import summarize_proposal_quality


def test_proposal_quality_summary_counts_readiness_and_missing_requirements() -> None:
    summary = summarize_proposal_quality(
        [
            {
                "proposal_id": "proposal_ready",
                "plugin_id": "generated.ready",
                "status": "approved",
                "friction": {"summary": "Repeated ready friction", "evidence": ["mission.ready"]},
                "quality_requirements": {
                    "risk_tier": "normal",
                    "tests": ["tests/test_ready.py"],
                    "docs": ["docs/ready.md"],
                    "validation_path": ["python -m pytest tests/test_ready.py"],
                    "known_limits": ["local only"],
                },
                "review": {"status": "approved", "receipt_id": "review_ready"},
                "validation": {
                    "validation_receipt_id": "plugin_validation_ready",
                    "validation_receipt_path": "data/artifacts/plugins/validations/plugin_validation_ready.json",
                },
            },
            {
                "proposal_id": "proposal_partial",
                "plugin_id": "generated.partial",
                "status": "staged",
                "friction": {"summary": "Repeated partial friction", "evidence": ["mission.partial"]},
                "quality_requirements": {
                    "risk_tier": "readonly",
                    "tests": ["tests/test_partial.py"],
                    "docs": ["docs/partial.md"],
                },
            },
            {
                "proposal_id": "proposal_weak",
                "plugin_id": "generated.weak",
                "status": "staged",
                "friction": {"summary": "", "evidence": []},
                "quality_requirements": {
                    "risk_tier": "experimental",
                    "tests": [],
                    "docs": [],
                    "validation_path": [],
                    "known_limits": [],
                },
            },
        ]
    )

    assert summary["kind"] == "plugin.proposal.quality_summary"
    assert summary["total"] == 3
    assert summary["ready_count"] == 1
    assert summary["blocked_count"] == 2
    assert summary["status_counts"] == {"approved": 1, "staged": 2}
    assert summary["risk_tier_counts"] == {"experimental": 1, "normal": 1, "readonly": 1}
    assert summary["review_status_counts"] == {"approved": 1, "staged": 2}
    assert summary["validation_receipt_counts"] == {"present": 1, "missing": 2}
    assert summary["missing_requirement_counts"] == {
        "friction_summary": 1,
        "proposal_evidence": 1,
        "tests": 1,
        "docs": 1,
        "risk_tier": 1,
        "validation_path": 2,
        "known_limits": 2,
    }
    assert summary["blocked_proposals"] == [
        {
            "proposal_id": "proposal_partial",
            "plugin_id": "generated.partial",
            "status": "staged",
            "missing_requirements": ["validation_path", "known_limits"],
        },
        {
            "proposal_id": "proposal_weak",
            "plugin_id": "generated.weak",
            "status": "staged",
            "missing_requirements": [
                "friction_summary",
                "proposal_evidence",
                "tests",
                "docs",
                "risk_tier",
                "validation_path",
                "known_limits",
            ],
        },
    ]
    assert summary["governance"] == {
        "analysis_only": True,
        "promotion_authority": False,
        "execution_authority": False,
        "approval_authority": False,
    }


def test_proposal_quality_summary_ignores_non_mapping_inputs() -> None:
    summary = summarize_proposal_quality([{}, [], "not a proposal"])

    assert summary["total"] == 1
    assert summary["ready_count"] == 0
    assert summary["blocked_count"] == 1
    assert summary["validation_receipt_counts"] == {"present": 0, "missing": 1}
    assert summary["blocked_proposals"] == [
        {
            "proposal_id": "",
            "plugin_id": "",
            "status": "unknown",
            "missing_requirements": [
                "proposal_id",
                "friction_summary",
                "proposal_evidence",
                "tests",
                "docs",
                "risk_tier",
                "validation_path",
                "known_limits",
            ],
        }
    ]
