from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

__all__ = [
    "analyze_capability_pack_promotion_rule_remediation",
    "analyze_capability_pack_promotion_rules",
    "canonical_capability_pack_promotion_rules",
]

_STAGE17_CAPABILITY_ECONOMY_STAGE = "Stage 17 / Capability Economy"
_CANONICAL_PROMOTION_RULES = [
    "metadata_receipt_before_promotion",
    "quality_standards_before_promotion",
    "operator_review_before_promotion",
]
_REMEDIATION_QUEUE_LIMIT = 50
_REMEDIATION_ACTION_BY_BLOCKER = {
    "pack_version_missing": "record_versioned_pack_metadata",
    "pack_metadata_receipt_missing": "write_pack_metadata_receipt",
    "promotion_rules_missing": "declare_canonical_promotion_rules",
    "canonical_promotion_rules_missing": "declare_canonical_promotion_rules",
    "pack_governance_missing": "attach_pack_governance",
    "tests_missing": "add_quality_tests",
    "docs_missing": "add_quality_docs",
    "validation_receipt_missing": "write_validation_receipt",
    "proposal_id_missing": "link_forge_proposal",
    "promotion_receipt_id_missing": "link_promotion_receipt",
}


def canonical_capability_pack_promotion_rules() -> list[str]:
    return list(_CANONICAL_PROMOTION_RULES)


def analyze_capability_pack_promotion_rules(entries: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    normalized = [_normalize_entry(entry) for entry in entries]
    normalized = [entry for entry in normalized if entry["capability"]]
    unpacked = [entry for entry in normalized if not entry["pack_id"]]
    packed = [entry for entry in normalized if entry["pack_id"]]
    packs = _pack_rules(packed)
    ready_pack_count = sum(1 for pack in packs if pack["ready"])
    return {
        "stage": _STAGE17_CAPABILITY_ECONOMY_STAGE,
        "status": "ready" if packs and ready_pack_count == len(packs) and not unpacked else "blocked",
        "total_entries": len(normalized),
        "pack_total": len(packs),
        "ready_pack_count": ready_pack_count,
        "blocked_pack_count": len(packs) - ready_pack_count,
        "unpacked_entry_count": len(unpacked),
        "packs": packs,
        "requirements": {
            "versioned_pack_metadata": True,
            "metadata_receipts_before_promotion": True,
            "explicit_promotion_rules": True,
            "pack_governance_travels": True,
            "quality_standards_before_promotion": True,
            "operator_review_before_promotion": True,
            "promotion_receipt_for_promoted_capabilities": True,
            "no_silent_promotion": True,
        },
        "governance": {
            "read_only": True,
            "does_not_write_receipts": True,
            "does_not_mutate_registry": True,
            "does_not_promote_capabilities": True,
            "does_not_enable_capabilities": True,
            "does_not_execute_capabilities": True,
            "promotion_authority": False,
            "execution_authority": False,
        },
        "next_smallest_truthful_gap": _next_gap(packs=packs, unpacked=unpacked),
    }


def analyze_capability_pack_promotion_rule_remediation(entries: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    normalized = [_normalize_entry(entry) for entry in entries]
    normalized = [entry for entry in normalized if entry["capability"]]
    unpacked = [entry for entry in normalized if not entry["pack_id"]]
    packed = [entry for entry in normalized if entry["pack_id"]]
    packs = _pack_rules(packed)
    ready_pack_count = sum(1 for pack in packs if pack["ready"] and not _missing_canonical_promotion_rules(pack))
    remediation_queue = [item for pack in packs if (item := _promotion_rule_remediation_item(pack)) is not None]
    remediation_queue = sorted(remediation_queue, key=_remediation_sort_key)
    visible_queue = remediation_queue[:_REMEDIATION_QUEUE_LIMIT]
    missing_rule_pack_count = sum(1 for item in remediation_queue if item["missing_promotion_rules"])
    return {
        "stage": _STAGE17_CAPABILITY_ECONOMY_STAGE,
        "status": "blocked" if unpacked or remediation_queue else ("ready" if packs else "empty"),
        "total_entries": len(normalized),
        "pack_total": len(packs),
        "ready_pack_count": ready_pack_count,
        "blocked_pack_count": len(packs) - ready_pack_count,
        "unpacked_entry_count": len(unpacked),
        "remediation_pack_count": len(remediation_queue),
        "remediation_queue_count": len(remediation_queue),
        "remediation_queue_truncated": len(remediation_queue) > len(visible_queue),
        "missing_rule_pack_count": missing_rule_pack_count,
        "missing_governance_pack_count": sum(1 for item in remediation_queue if item["missing_governance_fields"]),
        "missing_quality_pack_count": sum(1 for item in remediation_queue if item["missing_quality_evidence"]),
        "missing_receipt_pack_count": sum(1 for item in remediation_queue if item["missing_receipt_evidence"]),
        "canonical_promotion_rules": list(_CANONICAL_PROMOTION_RULES),
        "first_action": visible_queue[0]["first_action"] if visible_queue else "",
        "remediation_queue": visible_queue,
        "requirements": {
            "read_only_remediation_queue": True,
            "canonical_rules_declared_before_promotion": True,
            "metadata_receipt_rule_required": True,
            "quality_rule_required": True,
            "operator_review_rule_required": True,
            "remediation_does_not_write_registry": True,
        },
        "governance": {
            "read_only": True,
            "operator_facing": True,
            "does_not_write_receipts": True,
            "does_not_mutate_registry": True,
            "does_not_promote_capabilities": True,
            "does_not_enable_capabilities": True,
            "does_not_execute_capabilities": True,
            "promotion_authority": False,
            "execution_authority": False,
            "memory_write": False,
        },
        "next_smallest_truthful_gap": _remediation_next_gap(
            remediation_queue=remediation_queue,
            unpacked=unpacked,
            packs=packs,
        ),
    }


def _pack_rules(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for entry in entries:
        grouped.setdefault((entry["pack_id"], entry["pack_version"]), []).append(entry)

    packs: list[dict[str, Any]] = []
    for (pack_id, pack_version), grouped_entries in sorted(grouped.items()):
        blockers = _promotion_rule_blockers(grouped_entries)
        failing = [entry for entry in sorted(grouped_entries, key=_entry_sort_key) if _entry_rule_gaps(entry)]
        packs.append(
            {
                "pack_id": pack_id,
                "pack_version": pack_version,
                "pack_name": grouped_entries[0]["pack_name"],
                "status": "ready" if not blockers else "blocked",
                "ready": not blockers,
                "capability_count": len(grouped_entries),
                "blockers": blockers,
                "promotion_rules": sorted(
                    {rule for entry in grouped_entries for rule in entry["promotion_rules"] if rule}
                ),
                "explicit_rules_ready": all(bool(entry["promotion_rules"]) for entry in grouped_entries),
                "metadata_receipts_ready": all(
                    not _requires_pack_metadata_receipt(entry) or bool(entry["pack_metadata_receipt_id"])
                    for entry in grouped_entries
                ),
                "quality_standards_ready": all(_quality_ready(entry) for entry in grouped_entries),
                "governance_travels": all(bool(entry["pack_governance"]) for entry in grouped_entries),
                "operator_review_declared": any(_operator_review_declared(entry) for entry in grouped_entries),
                "promoted_capabilities_have_receipts": all(
                    entry["status"] != "promoted" or bool(entry["promotion_receipt_id"]) for entry in grouped_entries
                ),
                "failing_capabilities_sample": [_entry_rule_summary(entry) for entry in failing[:25]],
                "failing_capabilities_truncated": len(failing) > 25,
            }
        )
    return packs


def _promotion_rule_remediation_item(pack: Mapping[str, Any]) -> dict[str, Any] | None:
    missing_rules = _missing_canonical_promotion_rules(pack)
    blockers = _remediation_blockers(pack, missing_rules=missing_rules)
    if not blockers:
        return None
    missing_quality = [
        label
        for blocker, label in (
            ("tests_missing", "tests"),
            ("docs_missing", "docs"),
            ("validation_receipt_missing", "validation_receipt"),
            ("proposal_id_missing", "forge_proposal"),
            ("promotion_receipt_id_missing", "promotion_receipt"),
        )
        if blocker in blockers
    ]
    missing_receipts = [
        label
        for blocker, label in (
            ("pack_metadata_receipt_missing", "pack_metadata_receipt"),
            ("validation_receipt_missing", "validation_receipt"),
            ("promotion_receipt_id_missing", "promotion_receipt"),
        )
        if blocker in blockers
    ]
    missing_governance = []
    if not bool(pack.get("governance_travels")):
        missing_governance.append("pack_governance")
    if not bool(pack.get("operator_review_declared")):
        missing_governance.append("operator_review_required")
    return {
        "pack_id": str(pack.get("pack_id") or ""),
        "pack_version": str(pack.get("pack_version") or ""),
        "pack_name": str(pack.get("pack_name") or ""),
        "status": str(pack.get("status") or "blocked"),
        "ready": False,
        "capability_count": int(pack.get("capability_count") or 0),
        "blockers": blockers,
        "missing_promotion_rules": missing_rules,
        "missing_governance_fields": missing_governance,
        "missing_quality_evidence": missing_quality,
        "missing_receipt_evidence": missing_receipts,
        "first_action": _first_remediation_action(blockers),
        "promotion_rules": list(pack.get("promotion_rules") or []),
        "failing_capabilities_sample": list(pack.get("failing_capabilities_sample") or [])[:25],
    }


def _missing_canonical_promotion_rules(pack: Mapping[str, Any]) -> list[str]:
    observed = {str(rule).strip() for rule in list(pack.get("promotion_rules") or []) if str(rule).strip()}
    return [rule for rule in _CANONICAL_PROMOTION_RULES if rule not in observed]


def _remediation_blockers(pack: Mapping[str, Any], *, missing_rules: list[str]) -> list[str]:
    blockers = list(pack.get("blockers") or [])
    if missing_rules and "promotion_rules_missing" not in blockers:
        blockers.append("canonical_promotion_rules_missing")
    return blockers


def _first_remediation_action(blockers: list[str]) -> str:
    for blocker in _REMEDIATION_ACTION_BY_BLOCKER:
        if blocker in blockers:
            return _REMEDIATION_ACTION_BY_BLOCKER[blocker]
    return "review_capability_pack"


def _remediation_sort_key(item: Mapping[str, Any]) -> tuple[int, str, str]:
    blockers = list(item.get("blockers") or [])
    priority = min(
        (index for index, blocker in enumerate(_REMEDIATION_ACTION_BY_BLOCKER) if blocker in blockers),
        default=len(_REMEDIATION_ACTION_BY_BLOCKER),
    )
    return (priority, str(item.get("pack_id") or ""), str(item.get("pack_version") or ""))


def _promotion_rule_blockers(entries: list[dict[str, Any]]) -> list[str]:
    blockers: list[str] = []
    if any(not entry["pack_version"] for entry in entries):
        blockers.append("pack_version_missing")
    if any(_requires_pack_metadata_receipt(entry) and not entry["pack_metadata_receipt_id"] for entry in entries):
        blockers.append("pack_metadata_receipt_missing")
    if any(not entry["promotion_rules"] for entry in entries):
        blockers.append("promotion_rules_missing")
    if any(not entry["pack_governance"] for entry in entries):
        blockers.append("pack_governance_missing")
    if any(not entry["tests"] for entry in entries):
        blockers.append("tests_missing")
    if any(not entry["docs"] for entry in entries):
        blockers.append("docs_missing")
    if any(_requires_validation_receipt(entry) and not entry["validation_receipt_id"] for entry in entries):
        blockers.append("validation_receipt_missing")
    if any(entry["status"] == "staged" and not entry["proposal_id"] for entry in entries):
        blockers.append("proposal_id_missing")
    if any(entry["status"] == "promoted" and not entry["promotion_receipt_id"] for entry in entries):
        blockers.append("promotion_receipt_id_missing")
    return blockers


def _entry_rule_gaps(entry: Mapping[str, Any]) -> list[str]:
    gaps: list[str] = []
    if not entry.get("pack_version"):
        gaps.append("pack_version_missing")
    if _requires_pack_metadata_receipt(entry) and not entry.get("pack_metadata_receipt_id"):
        gaps.append("pack_metadata_receipt_missing")
    if not entry.get("promotion_rules"):
        gaps.append("promotion_rules_missing")
    if not entry.get("pack_governance"):
        gaps.append("pack_governance_missing")
    if not entry.get("tests"):
        gaps.append("tests_missing")
    if not entry.get("docs"):
        gaps.append("docs_missing")
    if _requires_validation_receipt(entry) and not entry.get("validation_receipt_id"):
        gaps.append("validation_receipt_missing")
    if entry.get("status") == "staged" and not entry.get("proposal_id"):
        gaps.append("proposal_id_missing")
    if entry.get("status") == "promoted" and not entry.get("promotion_receipt_id"):
        gaps.append("promotion_receipt_id_missing")
    return gaps


def _entry_rule_summary(entry: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "capability": str(entry.get("capability") or ""),
        "version": str(entry.get("version") or ""),
        "source": str(entry.get("source") or ""),
        "status": str(entry.get("status") or ""),
        "risk_tier": str(entry.get("risk_tier") or ""),
        "gaps": _entry_rule_gaps(entry),
    }


def _quality_ready(entry: Mapping[str, Any]) -> bool:
    return (
        bool(entry.get("tests"))
        and bool(entry.get("docs"))
        and (not _requires_validation_receipt(entry) or bool(entry.get("validation_receipt_id")))
        and (entry.get("status") != "staged" or bool(entry.get("proposal_id")))
        and (entry.get("status") != "promoted" or bool(entry.get("promotion_receipt_id")))
    )


def _operator_review_declared(entry: Mapping[str, Any]) -> bool:
    governance = entry.get("pack_governance")
    if not isinstance(governance, Mapping):
        return False
    return bool(
        governance.get("operator_review_required")
        or governance.get("approval_required")
        or governance.get("requires_operator_review")
    )


def _requires_validation_receipt(entry: Mapping[str, Any]) -> bool:
    return str(entry.get("source") or "") in {"forge", "generated"} and str(entry.get("status") or "") in {
        "staged",
        "promoted",
    }


def _requires_pack_metadata_receipt(entry: Mapping[str, Any]) -> bool:
    return _uses_projected_pack_metadata(entry)


def _uses_projected_pack_metadata(entry: Mapping[str, Any]) -> bool:
    return str(entry.get("pack_metadata_source") or "") == "legacy_generated_projection"


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
        "proposal_id": _text(entry.get("proposal_id")),
        "promotion_receipt_id": _text(entry.get("promotion_receipt_id")),
        "validation_receipt_id": _text(entry.get("validation_receipt_id") or metadata.get("validation_receipt_id")),
        "tests": _str_list(quality.get("tests")),
        "docs": _str_list(quality.get("docs")),
        "pack_id": _text(metadata.get("pack_id") or metadata.get("capability_pack_id")),
        "pack_version": _text(metadata.get("pack_version") or metadata.get("capability_pack_version")),
        "pack_name": _text(metadata.get("pack_name") or metadata.get("capability_pack_name")),
        "pack_metadata_source": _text(metadata.get("pack_metadata_source")),
        "pack_metadata_receipt_id": _text(metadata.get("pack_metadata_receipt_id")),
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
        ("pack_metadata_receipt_missing", "stage17_capability_pack_metadata_receipts"),
        ("promotion_rules_missing", "stage17_capability_pack_promotion_rules"),
        ("pack_governance_missing", "stage17_capability_pack_governance"),
        ("tests_missing", "stage17_capability_pack_quality_tests"),
        ("docs_missing", "stage17_capability_pack_quality_docs"),
        ("validation_receipt_missing", "stage17_capability_pack_validation_receipts"),
        ("proposal_id_missing", "stage17_capability_pack_lineage"),
        ("promotion_receipt_id_missing", "stage17_capability_pack_promotion_receipts"),
    ):
        if any(blocker in pack["blockers"] for pack in packs):
            return gap
    if packs:
        return "stage17_capability_pack_operator_surface"
    return "stage17_capability_pack_promotion_rules"


def _remediation_next_gap(
    *,
    remediation_queue: list[dict[str, Any]],
    unpacked: list[dict[str, Any]],
    packs: list[dict[str, Any]],
) -> str:
    if unpacked:
        return "stage17_versioned_capability_pack_metadata"
    if remediation_queue:
        return "stage17_capability_pack_promotion_rule_backlog_execution"
    if packs:
        return "stage17_capability_pack_operator_surface"
    return "stage17_capability_pack_promotion_rules"


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
