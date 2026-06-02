from __future__ import annotations

from collections.abc import Iterable, Mapping
import re
from typing import Any

__all__ = ["analyze_capability_pack_promotion_discipline"]

_STAGE17_CAPABILITY_ECONOMY_STAGE = "Stage 17 / Capability Economy"
_RECEIPT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,191}$")
_OPERATOR_REVIEW_RULES = {
    "operator_review_before_promotion",
    "explicit_operator_review_before_promotion",
    "operator_review_required_before_promotion",
}


def analyze_capability_pack_promotion_discipline(
    entries: Iterable[Mapping[str, Any]],
    *,
    available_proposal_ids: Iterable[str] = (),
    available_validation_receipt_ids: Iterable[str] = (),
    available_promotion_receipt_ids: Iterable[str] = (),
    operator_review_decisions: Iterable[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    proposal_ids = {_safe_identifier(value) for value in available_proposal_ids}
    proposal_ids.discard("")
    validation_receipt_ids = {_safe_identifier(value) for value in available_validation_receipt_ids}
    validation_receipt_ids.discard("")
    promotion_receipt_ids = {_safe_identifier(value) for value in available_promotion_receipt_ids}
    promotion_receipt_ids.discard("")
    approved_pack_reviews = _approved_pack_reviews(operator_review_decisions)

    normalized = [
        _normalize_entry(
            entry,
            available_proposal_ids=proposal_ids,
            available_validation_receipt_ids=validation_receipt_ids,
            available_promotion_receipt_ids=promotion_receipt_ids,
        )
        for entry in entries
    ]
    normalized = [entry for entry in normalized if entry["capability"]]
    unpacked = [entry for entry in normalized if not entry["pack_id"]]
    packed = [entry for entry in normalized if entry["pack_id"]]
    packs = _pack_discipline(packed, approved_pack_reviews=approved_pack_reviews)
    ready_pack_count = sum(1 for pack in packs if pack["ready"])
    blocked_pack_count = len(packs) - ready_pack_count

    return {
        "stage": _STAGE17_CAPABILITY_ECONOMY_STAGE,
        "status": "ready" if packs and ready_pack_count == len(packs) and not unpacked else "blocked",
        "total_entries": len(normalized),
        "pack_total": len(packs),
        "ready_pack_count": ready_pack_count,
        "blocked_pack_count": blocked_pack_count,
        "unpacked_entry_count": len(unpacked),
        "available_proposal_count": len(proposal_ids),
        "available_validation_receipt_count": len(validation_receipt_ids),
        "available_promotion_receipt_count": len(promotion_receipt_ids),
        "approved_pack_operator_review_count": len(approved_pack_reviews),
        "packs": packs,
        "unpacked_capabilities": [_entry_identity(entry) for entry in sorted(unpacked, key=_entry_sort_key)[:50]],
        "unpacked_capabilities_truncated": len(unpacked) > 50,
        "requirements": {
            "versioned_packs_required": True,
            "explicit_promotion_rules_required": True,
            "pack_governance_required": True,
            "tests_required": True,
            "docs_required": True,
            "generated_validation_receipts_must_exist": True,
            "staged_proposals_must_exist": True,
            "promoted_promotion_receipts_must_exist": True,
            "operator_review_required_for_staged_pack_promotion": True,
            "mixed_pack_lifecycle_requires_explicit_discipline_readback": True,
            "promotion_discipline_is_read_only": True,
        },
        "governance": {
            "read_only": True,
            "operator_facing": True,
            "does_not_read_proposal_bodies": True,
            "does_not_read_receipt_bodies": True,
            "does_not_write_receipts": True,
            "does_not_mutate_registry": True,
            "does_not_approve_proposals": True,
            "does_not_promote_capabilities": True,
            "does_not_enable_capabilities": True,
            "does_not_execute_capabilities": True,
            "proposal_approval_authority": False,
            "promotion_authority": False,
            "execution_authority": False,
            "memory_write": False,
        },
        "next_smallest_truthful_gap": _next_gap(packs=packs, unpacked=unpacked),
    }


def _pack_discipline(
    entries: list[dict[str, Any]],
    *,
    approved_pack_reviews: set[tuple[str, str]],
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for entry in entries:
        grouped.setdefault((entry["pack_id"], entry["pack_version"]), []).append(entry)

    packs: list[dict[str, Any]] = []
    for (pack_id, pack_version), grouped_entries in sorted(grouped.items()):
        sorted_entries = sorted(grouped_entries, key=_entry_sort_key)
        staged_entries = [entry for entry in grouped_entries if entry["status"] == "staged"]
        promoted_entries = [entry for entry in grouped_entries if entry["status"] == "promoted"]
        blockers = _pack_blockers(
            grouped_entries,
            approved_pack_reviews=approved_pack_reviews,
        )
        failing = [entry for entry in sorted_entries if _entry_gaps(entry)]
        review_approved = (pack_id, pack_version) in approved_pack_reviews
        packs.append(
            {
                "pack_id": pack_id,
                "pack_version": pack_version,
                "pack_name": grouped_entries[0]["pack_name"],
                "status": "ready" if not blockers else "blocked",
                "ready": not blockers,
                "capability_count": len(grouped_entries),
                "staged_capability_count": len(staged_entries),
                "promoted_capability_count": len(promoted_entries),
                "blockers": blockers,
                "promotion_rules_ready": all(bool(entry["promotion_rules"]) for entry in grouped_entries),
                "pack_governance_ready": all(bool(entry["pack_governance"]) for entry in grouped_entries),
                "quality_evidence_ready": all(entry["tests"] and entry["docs"] for entry in grouped_entries),
                "validation_receipts_ready": all(
                    not entry["requires_validation_receipt"] or entry["validation_receipt_present"]
                    for entry in grouped_entries
                ),
                "proposal_lineage_ready": all(
                    entry["status"] != "staged" or entry["proposal_present"] for entry in grouped_entries
                ),
                "promotion_receipts_ready": all(
                    entry["status"] != "promoted" or entry["promotion_receipt_present"] for entry in grouped_entries
                ),
                "operator_review_rule_declared": all(
                    _operator_review_rule_declared(entry) for entry in grouped_entries
                ),
                "operator_review_governance_declared": all(
                    _operator_review_governance_declared(entry) for entry in grouped_entries
                ),
                "operator_review_approved": review_approved,
                "lifecycle_mixed": bool(staged_entries and promoted_entries),
                "failing_capabilities_sample": [_entry_summary(entry) for entry in failing[:25]],
                "failing_capabilities_truncated": len(failing) > 25,
            }
        )
    return packs


def _pack_blockers(
    entries: list[dict[str, Any]],
    *,
    approved_pack_reviews: set[tuple[str, str]],
) -> list[str]:
    blockers: list[str] = []
    if any(not entry["pack_version"] for entry in entries):
        blockers.append("pack_version_missing")
    if any(not entry["promotion_rules"] for entry in entries):
        blockers.append("promotion_rules_missing")
    if any(not entry["pack_governance"] for entry in entries):
        blockers.append("pack_governance_missing")
    if any(not entry["tests"] for entry in entries):
        blockers.append("tests_missing")
    if any(not entry["docs"] for entry in entries):
        blockers.append("docs_missing")
    if any("validation_receipt_missing" in _entry_gaps(entry) for entry in entries):
        blockers.append("validation_receipt_missing")
    if any("validation_receipt_not_found" in _entry_gaps(entry) for entry in entries):
        blockers.append("validation_receipt_not_found")
    if any("proposal_id_missing" in _entry_gaps(entry) for entry in entries):
        blockers.append("proposal_id_missing")
    if any("proposal_not_found" in _entry_gaps(entry) for entry in entries):
        blockers.append("proposal_not_found")
    if any("promotion_receipt_id_missing" in _entry_gaps(entry) for entry in entries):
        blockers.append("promotion_receipt_id_missing")
    if any("promotion_receipt_not_found" in _entry_gaps(entry) for entry in entries):
        blockers.append("promotion_receipt_not_found")

    staged_entries = [entry for entry in entries if entry["status"] == "staged"]
    if staged_entries:
        if any(not _operator_review_rule_declared(entry) for entry in entries):
            blockers.append("operator_review_rule_missing")
        if any(not _operator_review_governance_declared(entry) for entry in entries):
            blockers.append("operator_review_governance_missing")
        pack_id = entries[0]["pack_id"]
        pack_version = entries[0]["pack_version"]
        if (pack_id, pack_version) not in approved_pack_reviews:
            blockers.append("operator_review_decision_missing")
    if staged_entries and any(entry["status"] == "promoted" for entry in entries):
        blockers.append("mixed_staged_and_promoted_pack")
    return blockers


def _entry_gaps(entry: Mapping[str, Any]) -> list[str]:
    gaps: list[str] = []
    if not entry.get("pack_version"):
        gaps.append("pack_version_missing")
    if not entry.get("promotion_rules"):
        gaps.append("promotion_rules_missing")
    if not entry.get("pack_governance"):
        gaps.append("pack_governance_missing")
    if not entry.get("tests"):
        gaps.append("tests_missing")
    if not entry.get("docs"):
        gaps.append("docs_missing")
    if entry.get("requires_validation_receipt"):
        if not entry.get("validation_receipt_id"):
            gaps.append("validation_receipt_missing")
        elif not entry.get("validation_receipt_present"):
            gaps.append("validation_receipt_not_found")
    if entry.get("status") == "staged":
        if not entry.get("proposal_id"):
            gaps.append("proposal_id_missing")
        elif not entry.get("proposal_present"):
            gaps.append("proposal_not_found")
    if entry.get("status") == "promoted":
        if not entry.get("promotion_receipt_id"):
            gaps.append("promotion_receipt_id_missing")
        elif not entry.get("promotion_receipt_present"):
            gaps.append("promotion_receipt_not_found")
    return gaps


def _entry_summary(entry: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "capability": str(entry.get("capability") or ""),
        "version": str(entry.get("version") or ""),
        "source": str(entry.get("source") or ""),
        "status": str(entry.get("status") or ""),
        "risk_tier": str(entry.get("risk_tier") or ""),
        "proposal_id": str(entry.get("proposal_id") or ""),
        "validation_receipt_id": str(entry.get("validation_receipt_id") or ""),
        "promotion_receipt_id": str(entry.get("promotion_receipt_id") or ""),
        "gaps": _entry_gaps(entry),
    }


def _normalize_entry(
    entry: Mapping[str, Any],
    *,
    available_proposal_ids: set[str],
    available_validation_receipt_ids: set[str],
    available_promotion_receipt_ids: set[str],
) -> dict[str, Any]:
    raw_quality = entry.get("quality")
    quality: Mapping[str, Any] = raw_quality if isinstance(raw_quality, Mapping) else {}
    raw_metadata = entry.get("metadata")
    metadata: Mapping[str, Any] = raw_metadata if isinstance(raw_metadata, Mapping) else {}
    source = _label(entry.get("source"))
    status = _label(entry.get("status"))
    proposal_id = _safe_identifier(entry.get("proposal_id") or metadata.get("proposal_id"))
    validation_receipt_id = _safe_identifier(
        entry.get("validation_receipt_id") or metadata.get("validation_receipt_id")
    )
    promotion_receipt_id = _safe_identifier(entry.get("promotion_receipt_id") or metadata.get("promotion_receipt_id"))
    return {
        "capability": _text(entry.get("capability")),
        "version": _text(entry.get("version"), fallback="0.1.0"),
        "source": source,
        "status": status,
        "risk_tier": _label(entry.get("risk_tier"), fallback="normal"),
        "proposal_id": proposal_id,
        "proposal_present": bool(proposal_id and proposal_id in available_proposal_ids),
        "validation_receipt_id": validation_receipt_id,
        "validation_receipt_present": bool(
            validation_receipt_id and validation_receipt_id in available_validation_receipt_ids
        ),
        "promotion_receipt_id": promotion_receipt_id,
        "promotion_receipt_present": bool(
            promotion_receipt_id and promotion_receipt_id in available_promotion_receipt_ids
        ),
        "requires_validation_receipt": source in {"forge", "generated"} and status in {"staged", "promoted"},
        "tests": _str_list(quality.get("tests") or metadata.get("tests") or metadata.get("test_refs")),
        "docs": _str_list(quality.get("docs") or metadata.get("docs") or metadata.get("documentation")),
        "pack_id": _text(metadata.get("pack_id") or metadata.get("capability_pack_id")),
        "pack_version": _text(metadata.get("pack_version") or metadata.get("capability_pack_version")),
        "pack_name": _text(metadata.get("pack_name") or metadata.get("capability_pack_name")),
        "promotion_rules": _str_list(metadata.get("promotion_rules") or metadata.get("promotion_rule_ids")),
        "pack_governance": _governance(metadata.get("pack_governance") or metadata.get("capability_pack_governance")),
    }


def _approved_pack_reviews(decisions: Iterable[Mapping[str, Any]]) -> set[tuple[str, str]]:
    approved: set[tuple[str, str]] = set()
    for decision in decisions:
        if not isinstance(decision, Mapping):
            continue
        status = _label(decision.get("status"))
        receipt_id = _safe_identifier(decision.get("receipt_id"))
        pack_id = _text(decision.get("pack_id"))
        pack_version = _text(decision.get("pack_version"))
        if status == "approved" and receipt_id and pack_id and pack_version:
            approved.add((pack_id, pack_version))
    return approved


def _operator_review_rule_declared(entry: Mapping[str, Any]) -> bool:
    rules = set(_str_list(entry.get("promotion_rules")))
    return bool(rules & _OPERATOR_REVIEW_RULES)


def _operator_review_governance_declared(entry: Mapping[str, Any]) -> bool:
    governance = entry.get("pack_governance")
    if not isinstance(governance, Mapping):
        return False
    return (
        _truthy(governance.get("operator_review_required"))
        or _truthy(governance.get("requires_operator_review"))
        or _truthy(governance.get("approval_required"))
    )


def _governance(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _entry_identity(entry: Mapping[str, Any]) -> dict[str, str]:
    return {
        "capability": str(entry.get("capability") or ""),
        "version": str(entry.get("version") or ""),
        "source": str(entry.get("source") or ""),
        "status": str(entry.get("status") or ""),
        "risk_tier": str(entry.get("risk_tier") or ""),
    }


def _entry_sort_key(entry: Mapping[str, Any]) -> tuple[str, str, str]:
    return (str(entry.get("capability") or ""), str(entry.get("version") or ""), str(entry.get("source") or ""))


def _next_gap(*, packs: list[dict[str, Any]], unpacked: list[dict[str, Any]]) -> str:
    if unpacked:
        return "stage17_versioned_capability_pack_metadata"
    for blocker, gap in (
        ("promotion_rules_missing", "stage17_capability_pack_promotion_rules"),
        ("pack_governance_missing", "stage17_capability_pack_governance"),
        ("tests_missing", "stage17_capability_pack_quality_tests"),
        ("docs_missing", "stage17_capability_pack_quality_docs"),
        ("validation_receipt_missing", "stage17_capability_pack_validation_receipts"),
        ("validation_receipt_not_found", "stage17_capability_pack_validation_receipts"),
        ("proposal_id_missing", "stage17_capability_pack_lineage"),
        ("proposal_not_found", "stage17_capability_pack_lineage"),
        ("promotion_receipt_id_missing", "stage17_capability_pack_promotion_receipts"),
        ("promotion_receipt_not_found", "stage17_capability_pack_promotion_receipts"),
        ("operator_review_rule_missing", "stage17_capability_pack_operator_review_contracts"),
        ("operator_review_governance_missing", "stage17_capability_pack_operator_review_contracts"),
        ("operator_review_decision_missing", "stage17_capability_pack_review_decisions"),
        ("mixed_staged_and_promoted_pack", "stage17_capability_pack_promotion_coherence"),
    ):
        if any(blocker in pack["blockers"] for pack in packs):
            return gap
    if packs:
        return "stage17_capability_library_operator_surface"
    return "stage17_versioned_capability_pack_metadata"


def _safe_identifier(value: Any) -> str:
    text = _text(value)
    if text.endswith(".json"):
        text = text[:-5]
    return text if _RECEIPT_ID_RE.match(text) else ""


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


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
