from __future__ import annotations

from francis.forge import analyze_proposal_quality


def test_proposal_quality_accepts_complete_forge_proposal_contract() -> None:
    analysis = analyze_proposal_quality(
        {
            "kind": "plugin.proposal",
            "proposal_id": "plugin_proposal_1",
            "plugin_id": "generated.echo",
            "status": "approved",
            "friction": {
                "summary": "Repeated operator handoff review",
                "evidence": ["mission.echo.repeat"],
            },
            "quality_requirements": {
                "risk_tier": "normal",
                "tests": ["tests/test_api_plugins.py::test_plugins_build"],
                "docs": ["data/artifacts/plugins/generated/echo/README.md"],
                "validation_path": ["python -m pytest tests/test_api_plugins.py"],
                "known_limits": ["local generated plugin only"],
            },
            "review": {"status": "approved", "receipt_id": "plugin_proposal_review_1"},
        }
    )

    assert analysis["kind"] == "plugin.proposal.quality_analysis"
    assert analysis["proposal_id"] == "plugin_proposal_1"
    assert analysis["plugin_id"] == "generated.echo"
    assert analysis["status"] == "approved"
    assert analysis["ready"] is True
    assert analysis["missing_requirements"] == []
    assert analysis["requirements"] == {
        "proposal_id": True,
        "friction_summary": True,
        "proposal_evidence": True,
        "tests": True,
        "docs": True,
        "risk_tier": True,
        "validation_path": True,
        "known_limits": True,
    }
    assert analysis["evidence"]["risk_tier"] == "normal"
    assert analysis["evidence"]["review_status"] == "approved"
    assert analysis["evidence"]["review_receipt_id"] == "plugin_proposal_review_1"
    assert analysis["governance"] == {
        "analysis_only": True,
        "promotion_authority": False,
        "execution_authority": False,
        "approval_authority": False,
        "next_step": "eligible_for_review_decision",
    }


def test_proposal_quality_reports_deterministic_missing_requirements() -> None:
    analysis = analyze_proposal_quality(
        {
            "kind": "plugin.proposal",
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
        }
    )

    assert analysis["ready"] is False
    assert analysis["missing_requirements"] == [
        "proposal_id",
        "friction_summary",
        "proposal_evidence",
        "tests",
        "docs",
        "risk_tier",
        "validation_path",
        "known_limits",
    ]
    assert analysis["requirements"]["risk_tier"] is False
    assert analysis["evidence"]["risk_tier"] == "experimental"
    assert analysis["evidence"]["review_status"] == "staged"
    assert analysis["governance"]["next_step"] == "review_missing_proposal_quality_requirements"


def test_proposal_quality_normalizes_aliases_without_requiring_review_approval() -> None:
    analysis = analyze_proposal_quality(
        {
            "id": "plugin_proposal_alias",
            "plugin_id": "generated.alias",
            "status": "staged",
            "proposal_evidence": "mission.alias.repeat",
            "friction": {"summary": "Repeated alias friction"},
            "quality": {
                "risk_tier": "readonly",
                "tests": "tests/test_alias.py",
                "docs": "docs/alias.md",
                "validation_path": "python -m pytest tests/test_alias.py",
                "limits": "read-only inspection only",
            },
        }
    )

    assert analysis["proposal_id"] == "plugin_proposal_alias"
    assert analysis["ready"] is True
    assert analysis["missing_requirements"] == []
    assert analysis["evidence"]["proposal_evidence"] == ["mission.alias.repeat"]
    assert analysis["evidence"]["tests"] == ["tests/test_alias.py"]
    assert analysis["evidence"]["known_limits"] == ["read-only inspection only"]
    assert analysis["evidence"]["review_status"] == "staged"
