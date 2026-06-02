from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

__all__ = ["analyze_capability_pack_operator_review"]

_STAGE17_CAPABILITY_ECONOMY_STAGE = "Stage 17 / Capability Economy"
_OPERATOR_REVIEW_RULES = {
    "operator_review_before_promotion",
    "explicit_operator_review_before_promotion",
    "operator_review_required_before_promotion",
}


def analyze_capability_pack_operator_review(entries: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    normalized = [_normalize_entry(entry) for entry in entries]
    normalized = [entry for entry in normalized if entry["capability"]]
    unpacked = [entry for entry in normalized if not entry["pack_id"]]
    packed = [entry for entry in normalized if entry["pack_id"]]
    packs = _pack_operator_reviews(packed)
    ready_pack_count = sum(1 for pack in packs if pack["operator_review_ready"])
    decision_required_count = sum(1 for pack in packs if pack["decision_required"])
    status = _status(
        packs=packs,
        unpacked=unpacked,
        ready_pack_count=ready_pack_count,
        decision_required_count=decision_required_count,
    )
    return {
        "stage": _STAGE17_CAPABILITY_ECONOMY_STAGE,
        "status": status,
        "total_entries": len(normalized),
        "pack_total": len(packs),
        "ready_pack_count": ready_pack_count,
        "blocked_pack_count": len(packs) - ready_pack_count,
        "decision_required_pack_count": decision_required_count,
        "unpacked_entry_count": len(unpacked),
        "review_queue_count": decision_required_count,
        "packs": packs,
        "decision_routes": {
            "proposal_review_route": "/forge/proposals/decision",
            "pack_review_decision_route": "/plugins/capabilities/packs/operator/review/decisions",
            "pack_review_decision_readback_route": "/plugins/capabilities/packs/operator/review/decisions",
            "promotion_route_after_review": "/plugins/enable",
            "review_readback_route": "/plugins/capabilities/packs/operator/review",
        },
        "requirements": {
            "operator_review_before_promotion_required": True,
            "operator_review_rule_required": True,
            "operator_review_governance_required": True,
            "quality_evidence_required_before_review": True,
            "validation_receipts_required_for_generated": True,
            "proposal_lineage_required_for_staged": True,
            "promotion_receipts_required_for_promoted": True,
            "review_decision_remains_separate_governed_action": True,
            "pack_review_receipt_required_before_pack_promotion": True,
        },
        "governance": {
            "read_only": True,
            "operator_facing": True,
            "does_not_read_proposal_bodies": True,
            "does_not_read_receipt_bodies": True,
            "does_not_write_reviews": True,
            "does_not_write_receipts": True,
            "does_not_mutate_registry": True,
            "does_not_approve_proposals": True,
            "does_not_promote_capabilities": True,
            "does_not_enable_capabilities": True,
            "does_not_execute_capabilities": True,
            "proposal_approval_authority": False,
            "promotion_authority": False,
            "execution_authority": False,
        },
        "next_smallest_truthful_gap": _next_gap(packs=packs, unpacked=unpacked),
    }


def _pack_operator_reviews(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for entry in entries:
        grouped.setdefault((entry["pack_id"], entry["pack_version"]), []).append(entry)

    packs: list[dict[str, Any]] = []
    for (pack_id, pack_version), grouped_entries in sorted(grouped.items()):
        sorted_entries = sorted(grouped_entries, key=_entry_sort_key)
        blockers = _review_blockers(grouped_entries)
        staged_entries = [entry for entry in grouped_entries if entry["status"] == "staged"]
        promoted_entries = [entry for entry in grouped_entries if entry["status"] == "promoted"]
        failing = [entry for entry in sorted_entries if _entry_review_gaps(entry)]
        ready = not blockers
        decision_required = ready and bool(staged_entries)
        packs.append(
            {
                "pack_id": pack_id,
                "pack_version": pack_version,
                "pack_name": grouped_entries[0]["pack_name"],
                "status": _pack_status(ready=ready, decision_required=decision_required),
                "operator_review_ready": ready,
                "decision_required": decision_required,
                "decision_kind": "staged_pack_promotion_review" if decision_required else "",
                "capability_count": len(grouped_entries),
                "staged_capability_count": len(staged_entries),
                "promoted_capability_count": len(promoted_entries),
                "blockers": blockers,
                "operator_review_rule_declared": all(
                    _operator_review_rule_declared(entry) for entry in grouped_entries
                ),
                "operator_review_governance_declared": all(
                    _operator_review_governance_declared(entry) for entry in grouped_entries
                ),
                "quality_evidence_ready": all(_quality_ready(entry) for entry in grouped_entries),
                "proposal_lineage_ready": all(
                    entry["status"] != "staged" or bool(entry["proposal_id"]) for entry in grouped_entries
                ),
                "promotion_receipts_ready": all(
                    entry["status"] != "promoted" or bool(entry["promotion_receipt_id"]) for entry in grouped_entries
                ),
                "validation_receipts_ready": all(
                    not _requires_validation_receipt(entry) or bool(entry["validation_receipt_id"])
                    for entry in grouped_entries
                ),
                "tested_count": sum(1 for entry in grouped_entries if entry["tests"]),
                "documented_count": sum(1 for entry in grouped_entries if entry["docs"]),
                "validation_receipt_count": sum(1 for entry in grouped_entries if entry["validation_receipt_id"]),
                "proposal_lineage_count": sum(1 for entry in grouped_entries if entry["proposal_id"]),
                "promotion_receipt_count": sum(1 for entry in grouped_entries if entry["promotion_receipt_id"]),
                "review_items_sample": [_entry_review_summary(entry) for entry in sorted_entries[:25]],
                "review_items_truncated": len(sorted_entries) > 25,
                "failing_capabilities_sample": [_entry_review_summary(entry) for entry in failing[:25]],
                "failing_capabilities_truncated": len(failing) > 25,
            }
        )
    return packs


def _review_blockers(entries: list[dict[str, Any]]) -> list[str]:
    blockers: list[str] = []
    if any(not entry["pack_version"] for entry in entries):
        blockers.append("pack_version_missing")
    if any(not _operator_review_rule_declared(entry) for entry in entries):
        blockers.append("operator_review_rule_missing")
    if any(not _operator_review_governance_declared(entry) for entry in entries):
        blockers.append("operator_review_governance_missing")
    if any(not entry["tests"] for entry in entries):
        blockers.append("tests_missing")
    if any(not entry["docs"] for entry in entries):
        blockers.append("docs_missing")
    if any(_requires_validation_receipt(entry) and not entry["validation_receipt_id"] for entry in entries):
        blockers.append("validation_receipt_missing")
    if any(entry["status"] == "staged" and not entry["proposal_id"] for entry in entries):
        blockers.append("proposal_lineage_missing")
    if any(entry["status"] == "promoted" and not entry["promotion_receipt_id"] for entry in entries):
        blockers.append("promotion_receipt_missing")
    return blockers


def _entry_review_gaps(entry: Mapping[str, Any]) -> list[str]:
    gaps: list[str] = []
    if not entry.get("pack_version"):
        gaps.append("pack_version_missing")
    if not _operator_review_rule_declared(entry):
        gaps.append("operator_review_rule_missing")
    if not _operator_review_governance_declared(entry):
        gaps.append("operator_review_governance_missing")
    if not entry.get("tests"):
        gaps.append("tests_missing")
    if not entry.get("docs"):
        gaps.append("docs_missing")
    if _requires_validation_receipt(entry) and not entry.get("validation_receipt_id"):
        gaps.append("validation_receipt_missing")
    if entry.get("status") == "staged" and not entry.get("proposal_id"):
        gaps.append("proposal_lineage_missing")
    if entry.get("status") == "promoted" and not entry.get("promotion_receipt_id"):
        gaps.append("promotion_receipt_missing")
    return gaps


def _entry_review_summary(entry: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "capability": str(entry.get("capability") or ""),
        "version": str(entry.get("version") or ""),
        "source": str(entry.get("source") or ""),
        "status": str(entry.get("status") or ""),
        "risk_tier": str(entry.get("risk_tier") or ""),
        "proposal_id": str(entry.get("proposal_id") or ""),
        "validation_receipt_id": str(entry.get("validation_receipt_id") or ""),
        "promotion_receipt_id": str(entry.get("promotion_receipt_id") or ""),
        "gaps": _entry_review_gaps(entry),
    }


def _status(
    *,
    packs: list[dict[str, Any]],
    unpacked: list[dict[str, Any]],
    ready_pack_count: int,
    decision_required_count: int,
) -> str:
    if not packs:
        return "empty"
    if unpacked or ready_pack_count != len(packs):
        return "blocked"
    if decision_required_count > 0:
        return "ready_for_operator_review"
    return "promotion_review_evidence_ready"


def _pack_status(*, ready: bool, decision_required: bool) -> str:
    if not ready:
        return "blocked"
    if decision_required:
        return "ready_for_operator_review"
    return "promotion_review_evidence_ready"


def _quality_ready(entry: Mapping[str, Any]) -> bool:
    return (
        bool(entry.get("tests"))
        and bool(entry.get("docs"))
        and (not _requires_validation_receipt(entry) or bool(entry.get("validation_receipt_id")))
    )


def _operator_review_rule_declared(entry: Mapping[str, Any]) -> bool:
    rules = entry.get("promotion_rules")
    return (
        any(str(rule).strip() in _OPERATOR_REVIEW_RULES for rule in rules if str(rule).strip())
        if isinstance(rules, list)
        else False
    )


def _operator_review_governance_declared(entry: Mapping[str, Any]) -> bool:
    governance = entry.get("pack_governance")
    if not isinstance(governance, Mapping):
        return False
    return bool(
        governance.get("operator_review_required")
        or governance.get("requires_operator_review")
        or governance.get("approval_required")
    )


def _requires_validation_receipt(entry: Mapping[str, Any]) -> bool:
    return str(entry.get("source") or "") in {"forge", "generated"} and str(entry.get("status") or "") in {
        "staged",
        "promoted",
    }


def _normalize_entry(entry: Mapping[str, Any]) -> dict[str, Any]:
    raw_quality = entry.get("quality")
    quality: Mapping[str, Any] = raw_quality if isinstance(raw_quality, Mapping) else {}
    raw_metadata = entry.get("metadata")
    metadata: Mapping[str, Any] = raw_metadata if isinstance(raw_metadata, Mapping) else {}
    return {
        "capability": _text(entry.get("capability")),
        "version": _text(entry.get("version"), fallback="0.1.0"),
        "source": _label(entry.get("source")),
        "status": _label(entry.get("status")),
        "risk_tier": _label(entry.get("risk_tier"), fallback="normal"),
        "proposal_id": _text(
            entry.get("proposal_id") or metadata.get("proposal_id") or metadata.get("forge_proposal_id")
        ),
        "promotion_receipt_id": _text(entry.get("promotion_receipt_id") or metadata.get("promotion_receipt_id")),
        "validation_receipt_id": _text(entry.get("validation_receipt_id") or metadata.get("validation_receipt_id")),
        "tests": _str_list(quality.get("tests")),
        "docs": _str_list(quality.get("docs")),
        "pack_id": _text(metadata.get("pack_id") or metadata.get("capability_pack_id")),
        "pack_version": _text(metadata.get("pack_version") or metadata.get("capability_pack_version")),
        "pack_name": _text(metadata.get("pack_name") or metadata.get("capability_pack_name")),
        "promotion_rules": _str_list(metadata.get("promotion_rules") or metadata.get("promotion_rule_ids")),
        "pack_governance": _governance(metadata.get("pack_governance") or metadata.get("capability_pack_governance")),
    }


def _entry_sort_key(entry: Mapping[str, Any]) -> tuple[str, str, str]:
    return (str(entry.get("capability") or ""), str(entry.get("version") or ""), str(entry.get("source") or ""))


def _governance(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _next_gap(*, packs: list[dict[str, Any]], unpacked: list[dict[str, Any]]) -> str:
    if unpacked:
        return "stage17_versioned_capability_pack_metadata"
    for blocker, gap in (
        ("pack_version_missing", "stage17_versioned_capability_pack_metadata"),
        ("operator_review_rule_missing", "stage17_capability_pack_operator_review_contracts"),
        ("operator_review_governance_missing", "stage17_capability_pack_operator_review_contracts"),
        ("tests_missing", "stage17_capability_pack_quality_tests"),
        ("docs_missing", "stage17_capability_pack_quality_docs"),
        ("validation_receipt_missing", "stage17_capability_pack_validation_receipts"),
        ("proposal_lineage_missing", "stage17_capability_pack_lineage"),
        ("promotion_receipt_missing", "stage17_capability_pack_promotion_receipts"),
    ):
        if any(blocker in pack["blockers"] for pack in packs):
            return gap
    if packs:
        return "stage17_capability_pack_review_decisions"
    return "stage17_capability_pack_operator_surface"


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
    if isinstance(value, Mapping):
        return [str(key).strip() for key in sorted(value) if str(key).strip()]
    if isinstance(value, (list, tuple, set)):
        return [text for item in value if (text := str(item).strip())]
    text = str(value).strip()
    return [text] if text else []
