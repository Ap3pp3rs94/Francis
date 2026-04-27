from __future__ import annotations

from collections.abc import Mapping
from typing import Any

__all__ = ["analyze_proposal_quality"]

_ALLOWED_RISK_TIERS = {"readonly", "normal", "critical", "safety_critical"}
_REQUIREMENT_ORDER = (
    "proposal_id",
    "friction_summary",
    "proposal_evidence",
    "tests",
    "docs",
    "risk_tier",
    "validation_path",
    "known_limits",
)


def analyze_proposal_quality(proposal: Mapping[str, Any]) -> dict[str, Any]:
    friction = _mapping(proposal.get("friction"))
    quality = _mapping(proposal.get("quality_requirements") or proposal.get("quality"))
    review = _mapping(proposal.get("review"))

    proposal_id = _text(proposal.get("proposal_id") or proposal.get("id"))
    plugin_id = _text(proposal.get("plugin_id"))
    status = _label(proposal.get("status"))
    risk_tier = _label(quality.get("risk_tier"), fallback="")
    review_status = _label(review.get("status") or proposal.get("review_status") or status)
    review_receipt_id = _text(proposal.get("review_receipt_id") or review.get("receipt_id"))

    requirements = {
        "proposal_id": bool(proposal_id),
        "friction_summary": bool(_text(friction.get("summary"))),
        "proposal_evidence": bool(_str_list(friction.get("evidence") or proposal.get("proposal_evidence"))),
        "tests": bool(_str_list(quality.get("tests") or proposal.get("tests"))),
        "docs": bool(_str_list(quality.get("docs") or proposal.get("docs"))),
        "risk_tier": risk_tier in _ALLOWED_RISK_TIERS,
        "validation_path": bool(_str_list(quality.get("validation_path") or proposal.get("validation_path"))),
        "known_limits": bool(
            _str_list(quality.get("known_limits") or quality.get("limits") or proposal.get("known_limits"))
        ),
    }
    missing = [key for key in _REQUIREMENT_ORDER if not requirements[key]]

    return {
        "kind": "plugin.proposal.quality_analysis",
        "proposal_id": proposal_id,
        "plugin_id": plugin_id,
        "status": status,
        "ready": not missing,
        "requirements": requirements,
        "missing_requirements": missing,
        "evidence": {
            "risk_tier": risk_tier,
            "review_status": review_status,
            "review_receipt_id": review_receipt_id,
            "proposal_evidence": _str_list(friction.get("evidence") or proposal.get("proposal_evidence")),
            "tests": _str_list(quality.get("tests") or proposal.get("tests")),
            "docs": _str_list(quality.get("docs") or proposal.get("docs")),
            "validation_path": _str_list(quality.get("validation_path") or proposal.get("validation_path")),
            "known_limits": _str_list(
                quality.get("known_limits") or quality.get("limits") or proposal.get("known_limits")
            ),
        },
        "governance": {
            "analysis_only": True,
            "promotion_authority": False,
            "execution_authority": False,
            "approval_authority": False,
            "next_step": "review_missing_proposal_quality_requirements" if missing else "eligible_for_review_decision",
        },
    }


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _text(value: Any, *, fallback: str = "") -> str:
    text = str(value or "").strip()
    return text or fallback


def _label(value: Any, *, fallback: str = "unknown") -> str:
    return _text(value, fallback=fallback).lower()


def _str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, (list, tuple, set)):
        return [text for item in value if (text := str(item).strip())]
    text = str(value).strip()
    return [text] if text else []
