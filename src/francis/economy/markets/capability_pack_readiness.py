from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

__all__ = ["analyze_capability_pack_readiness"]

_STAGE17_CAPABILITY_ECONOMY_STAGE = "Stage 17 / Capability Economy"


def analyze_capability_pack_readiness(entries: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    normalized = [_normalize_entry(entry) for entry in entries]
    normalized = [entry for entry in normalized if entry["capability"]]
    packed = [entry for entry in normalized if entry["pack_id"]]
    unpacked = [entry for entry in normalized if not entry["pack_id"]]
    packs = _pack_readiness(packed)
    ready_pack_count = sum(1 for pack in packs if pack["ready"])

    return {
        "stage": _STAGE17_CAPABILITY_ECONOMY_STAGE,
        "status": "ready" if packs and ready_pack_count == len(packs) and not unpacked else "blocked",
        "total_entries": len(normalized),
        "packed_entry_count": len(packed),
        "unpacked_entry_count": len(unpacked),
        "pack_total": len(packs),
        "ready_pack_count": ready_pack_count,
        "blocked_pack_count": len(packs) - ready_pack_count,
        "packs": packs,
        "unpacked_capabilities": [_entry_identity(entry) for entry in sorted(unpacked, key=_entry_sort_key)[:50]],
        "unpacked_capabilities_truncated": len(unpacked) > 50,
        "governance": {
            "read_only": True,
            "versioned_packs_required": True,
            "promotion_rules_required": True,
            "quality_standards_required": True,
            "governance_must_travel_with_pack": True,
            "does_not_promote_capabilities": True,
            "does_not_install_capabilities": True,
            "does_not_execute_capabilities": True,
            "does_not_write_receipts": True,
        },
        "next_smallest_truthful_gap": _next_gap(packs=packs, unpacked=unpacked),
    }


def _pack_readiness(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for entry in entries:
        grouped.setdefault((entry["pack_id"], entry["pack_version"]), []).append(entry)

    packs: list[dict[str, Any]] = []
    for (pack_id, pack_version), grouped_entries in sorted(grouped.items()):
        blockers = _pack_blockers(grouped_entries)
        capabilities = [_entry_identity(entry) for entry in sorted(grouped_entries, key=_entry_sort_key)]
        packs.append(
            {
                "pack_id": pack_id,
                "pack_version": pack_version,
                "pack_name": grouped_entries[0]["pack_name"],
                "status": "ready" if not blockers else "blocked",
                "ready": not blockers,
                "capability_count": len(grouped_entries),
                "capabilities": capabilities,
                "blockers": blockers,
                "versioned_pack": bool(pack_id and pack_version),
                "projected_metadata": any(_uses_projected_pack_metadata(entry) for entry in grouped_entries),
                "metadata_receipts_ready": all(
                    not _requires_pack_metadata_receipt(entry) or bool(entry["pack_metadata_receipt_id"])
                    for entry in grouped_entries
                ),
                "promotion_rules_ready": all(bool(entry["promotion_rules"]) for entry in grouped_entries),
                "quality_standards_ready": all(_quality_ready(entry) for entry in grouped_entries),
                "governance_travels": all(bool(entry["pack_governance"]) for entry in grouped_entries),
                "reusable_asset": not blockers,
            }
        )
    return packs


def _pack_blockers(entries: list[dict[str, Any]]) -> list[str]:
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


def _quality_ready(entry: Mapping[str, Any]) -> bool:
    return (
        bool(entry["tests"])
        and bool(entry["docs"])
        and (not _requires_validation_receipt(entry) or bool(entry["validation_receipt_id"]))
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
        ("tests_missing", "stage17_capability_pack_quality_standards"),
        ("docs_missing", "stage17_capability_pack_quality_standards"),
        ("validation_receipt_missing", "stage17_capability_pack_validation_receipts"),
        ("proposal_id_missing", "stage17_capability_pack_lineage"),
        ("promotion_receipt_id_missing", "stage17_capability_pack_promotion_receipts"),
    ):
        if any(blocker in pack["blockers"] for pack in packs):
            return gap
    if packs:
        return "stage17_capability_pack_operator_surface"
    return "stage17_versioned_capability_pack_metadata"


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
