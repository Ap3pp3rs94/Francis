from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

__all__ = ["analyze_capability_pack_quality_standards"]

_STAGE17_CAPABILITY_ECONOMY_STAGE = "Stage 17 / Capability Economy"


def analyze_capability_pack_quality_standards(entries: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    normalized = [_normalize_entry(entry) for entry in entries]
    normalized = [entry for entry in normalized if entry["capability"]]
    unpacked = [entry for entry in normalized if not entry["pack_id"]]
    packed = [entry for entry in normalized if entry["pack_id"]]
    packs = _pack_quality(packed)
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
        "standards": {
            "tests_required": True,
            "docs_required": True,
            "validation_receipts_required_for_generated": True,
            "proposal_lineage_required_for_staged": True,
            "promotion_receipts_required_for_promoted": True,
            "known_limits_recommended": True,
            "risk_tier_required": True,
        },
        "governance": {
            "read_only": True,
            "does_not_write_receipts": True,
            "does_not_mutate_registry": True,
            "does_not_promote_capabilities": True,
            "does_not_execute_capabilities": True,
            "quality_evidence_required_before_promotion": True,
        },
        "next_smallest_truthful_gap": _next_gap(packs=packs, unpacked=unpacked),
    }


def _pack_quality(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for entry in entries:
        grouped.setdefault((entry["pack_id"], entry["pack_version"]), []).append(entry)

    out: list[dict[str, Any]] = []
    for (pack_id, pack_version), grouped_entries in sorted(grouped.items()):
        blockers = _quality_blockers(grouped_entries)
        failing = [entry for entry in sorted(grouped_entries, key=_entry_sort_key) if _entry_quality_gaps(entry)]
        out.append(
            {
                "pack_id": pack_id,
                "pack_version": pack_version,
                "pack_name": grouped_entries[0]["pack_name"],
                "status": "ready" if not blockers else "blocked",
                "ready": not blockers,
                "capability_count": len(grouped_entries),
                "blockers": blockers,
                "tested_count": sum(1 for entry in grouped_entries if entry["tests"]),
                "documented_count": sum(1 for entry in grouped_entries if entry["docs"]),
                "validation_receipt_count": sum(1 for entry in grouped_entries if entry["validation_receipt_id"]),
                "proposal_lineage_count": sum(1 for entry in grouped_entries if entry["proposal_id"]),
                "promotion_receipt_count": sum(1 for entry in grouped_entries if entry["promotion_receipt_id"]),
                "known_limits_count": sum(1 for entry in grouped_entries if entry["known_limits"]),
                "risk_tiers": sorted({entry["risk_tier"] for entry in grouped_entries if entry["risk_tier"]}),
                "failing_capabilities_sample": [_entry_quality_summary(entry) for entry in failing[:25]],
                "failing_capabilities_truncated": len(failing) > 25,
            }
        )
    return out


def _quality_blockers(entries: list[dict[str, Any]]) -> list[str]:
    blockers: list[str] = []
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
    if any(not entry["risk_tier"] for entry in entries):
        blockers.append("risk_tier_missing")
    return blockers


def _entry_quality_gaps(entry: Mapping[str, Any]) -> list[str]:
    gaps: list[str] = []
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
    if not entry.get("risk_tier"):
        gaps.append("risk_tier_missing")
    return gaps


def _entry_quality_summary(entry: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "capability": str(entry.get("capability") or ""),
        "version": str(entry.get("version") or ""),
        "source": str(entry.get("source") or ""),
        "status": str(entry.get("status") or ""),
        "risk_tier": str(entry.get("risk_tier") or ""),
        "gaps": _entry_quality_gaps(entry),
    }


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
        "proposal_id": _text(entry.get("proposal_id")),
        "promotion_receipt_id": _text(entry.get("promotion_receipt_id")),
        "validation_receipt_id": _text(entry.get("validation_receipt_id") or metadata.get("validation_receipt_id")),
        "tests": _str_list(quality.get("tests")),
        "docs": _str_list(quality.get("docs")),
        "known_limits": _str_list(metadata.get("known_limits")),
        "pack_id": _text(metadata.get("pack_id") or metadata.get("capability_pack_id")),
        "pack_version": _text(metadata.get("pack_version") or metadata.get("capability_pack_version")),
        "pack_name": _text(metadata.get("pack_name") or metadata.get("capability_pack_name")),
    }


def _entry_sort_key(entry: Mapping[str, Any]) -> tuple[str, str, str]:
    return (str(entry.get("capability") or ""), str(entry.get("version") or ""), str(entry.get("source") or ""))


def _next_gap(*, packs: list[dict[str, Any]], unpacked: list[dict[str, Any]]) -> str:
    if unpacked:
        return "stage17_versioned_capability_pack_metadata"
    for blocker, gap in (
        ("tests_missing", "stage17_capability_pack_quality_tests"),
        ("docs_missing", "stage17_capability_pack_quality_docs"),
        ("validation_receipt_missing", "stage17_capability_pack_validation_receipts"),
        ("proposal_id_missing", "stage17_capability_pack_lineage"),
        ("promotion_receipt_id_missing", "stage17_capability_pack_promotion_receipts"),
        ("risk_tier_missing", "stage17_capability_pack_risk_tier"),
    ):
        if any(blocker in pack["blockers"] for pack in packs):
            return gap
    if packs:
        return "stage17_capability_pack_promotion_rules"
    return "stage17_capability_pack_quality_standards"


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
