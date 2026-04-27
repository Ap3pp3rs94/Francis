from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from .proposal_quality import analyze_proposal_quality

__all__ = ["summarize_proposal_quality"]

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


def summarize_proposal_quality(proposals: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    analyses = [analyze_proposal_quality(proposal) for proposal in proposals if isinstance(proposal, Mapping)]
    blocked = [analysis for analysis in analyses if not bool(analysis.get("ready"))]

    return {
        "kind": "plugin.proposal.quality_summary",
        "total": len(analyses),
        "ready_count": sum(1 for analysis in analyses if bool(analysis.get("ready"))),
        "blocked_count": len(blocked),
        "status_counts": _counts(_text(analysis.get("status")) for analysis in analyses),
        "risk_tier_counts": _counts(_text(_evidence(analysis).get("risk_tier")) for analysis in analyses),
        "review_status_counts": _counts(_text(_evidence(analysis).get("review_status")) for analysis in analyses),
        "validation_receipt_counts": _validation_receipt_counts(analyses),
        "missing_requirement_counts": _missing_requirement_counts(blocked),
        "blocked_proposals": _blocked_proposals(blocked),
        "governance": {
            "analysis_only": True,
            "promotion_authority": False,
            "execution_authority": False,
            "approval_authority": False,
        },
    }


def _validation_receipt_counts(analyses: list[dict[str, Any]]) -> dict[str, int]:
    present = sum(1 for analysis in analyses if bool(_evidence(analysis).get("validation_receipt_present")))
    return {
        "present": present,
        "missing": len(analyses) - present,
    }


def _missing_requirement_counts(analyses: list[dict[str, Any]]) -> dict[str, int]:
    counts = {key: 0 for key in _REQUIREMENT_ORDER}
    for analysis in analyses:
        for key in _str_list(analysis.get("missing_requirements")):
            if key in counts:
                counts[key] += 1
    return {key: count for key, count in counts.items() if count > 0}


def _blocked_proposals(analyses: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for analysis in analyses:
        items.append(
            {
                "proposal_id": _text(analysis.get("proposal_id")),
                "plugin_id": _text(analysis.get("plugin_id")),
                "status": _text(analysis.get("status")),
                "missing_requirements": _str_list(analysis.get("missing_requirements")),
            }
        )
    return sorted(items, key=lambda item: (item["proposal_id"], item["plugin_id"], item["status"]))


def _evidence(analysis: Mapping[str, Any]) -> Mapping[str, Any]:
    evidence = analysis.get("evidence")
    return evidence if isinstance(evidence, Mapping) else {}


def _counts(values: Iterable[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        if not value:
            continue
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def _text(value: Any) -> str:
    return str(value or "").strip()


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
