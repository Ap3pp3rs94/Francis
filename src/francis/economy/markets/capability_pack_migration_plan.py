from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from .capability_pack_readiness import analyze_capability_pack_readiness

__all__ = ["analyze_capability_pack_migration_plan"]

_STAGE17_CAPABILITY_ECONOMY_STAGE = "Stage 17 / Capability Economy"
_METADATA_RECEIPT_BLOCKER = "pack_metadata_receipt_missing"


def analyze_capability_pack_migration_plan(entries: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    all_entries = [_normalize_entry(entry) for entry in entries]
    readiness = analyze_capability_pack_readiness(all_entries)
    candidates = _metadata_receipt_candidates(readiness.get("packs"), all_entries)
    return {
        "stage": _STAGE17_CAPABILITY_ECONOMY_STAGE,
        "status": "ready_for_metadata_receipt_review" if candidates else "blocked",
        "candidate_total": len(candidates),
        "candidates": candidates,
        "readiness_status": str(readiness.get("status") or "blocked"),
        "readiness_next_smallest_truthful_gap": str(readiness.get("next_smallest_truthful_gap") or ""),
        "write_route": "/plugins/capabilities/packs/metadata/receipts",
        "read_route": "/plugins/capabilities/packs/metadata/receipts",
        "governance": {
            "read_only": True,
            "does_not_write_receipts": True,
            "does_not_mutate_registry": True,
            "does_not_promote_capabilities": True,
            "does_not_execute_capabilities": True,
            "operator_review_required": True,
            "metadata_receipts_required_before_promotion": True,
        },
        "next_smallest_truthful_gap": _next_gap(candidates=candidates, readiness=readiness),
    }


def _metadata_receipt_candidates(
    raw_packs: Any,
    entries: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    packs = raw_packs if isinstance(raw_packs, list) else []
    by_pack: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for entry in entries:
        pack_id = str(entry.get("pack_id") or "")
        if not pack_id:
            continue
        by_pack.setdefault((pack_id, str(entry.get("pack_version") or "")), []).append(entry)

    out: list[dict[str, Any]] = []
    for pack in packs:
        if not isinstance(pack, Mapping):
            continue
        blockers = [str(item) for item in pack.get("blockers") or [] if str(item)]
        if _METADATA_RECEIPT_BLOCKER not in blockers:
            continue
        pack_id = str(pack.get("pack_id") or "")
        pack_version = str(pack.get("pack_version") or "")
        entries_for_pack = sorted(by_pack.get((pack_id, pack_version), []), key=_entry_sort_key)
        capability_ids = [str(entry.get("capability") or "") for entry in entries_for_pack if entry.get("capability")]
        out.append(
            {
                "pack_id": pack_id,
                "pack_version": pack_version,
                "pack_name": str(pack.get("pack_name") or pack_id),
                "capability_count": len(capability_ids),
                "capability_ids_sample": capability_ids[:25],
                "capability_ids_truncated": len(capability_ids) > 25,
                "blockers": blockers,
                "suggested_promotion_rules": [
                    "metadata_receipt_before_promotion",
                    "quality_standards_before_promotion",
                    "validation_receipts_before_promotion",
                    "operator_review_before_promotion",
                ],
                "suggested_pack_governance": {
                    "migration_pack": True,
                    "source": "legacy_generated_projection",
                    "risk_tier": "normal",
                    "operator_review_required": True,
                    "promotion_authority": False,
                    "execution_authority": False,
                },
                "requires_explicit_capability_id_selection": True,
                "write_route": "/plugins/capabilities/packs/metadata/receipts",
            }
        )
    return out


def _normalize_entry(entry: Mapping[str, Any]) -> dict[str, Any]:
    raw_metadata = entry.get("metadata")
    metadata: Mapping[str, Any] = raw_metadata if isinstance(raw_metadata, Mapping) else {}
    return {
        "capability": _text(entry.get("capability")),
        "version": _text(entry.get("version"), fallback="0.1.0"),
        "source": _text(entry.get("source"), fallback="unknown"),
        "status": _text(entry.get("status"), fallback="unknown"),
        "risk_tier": _text(entry.get("risk_tier"), fallback="normal"),
        "quality": entry.get("quality") if isinstance(entry.get("quality"), Mapping) else {},
        "metadata": dict(metadata),
        "pack_id": _text(metadata.get("pack_id") or metadata.get("capability_pack_id")),
        "pack_version": _text(metadata.get("pack_version") or metadata.get("capability_pack_version")),
    }


def _entry_sort_key(entry: Mapping[str, Any]) -> tuple[str, str, str]:
    return (str(entry.get("capability") or ""), str(entry.get("version") or ""), str(entry.get("source") or ""))


def _next_gap(*, candidates: list[dict[str, Any]], readiness: Mapping[str, Any]) -> str:
    if candidates:
        return "stage17_capability_pack_metadata_receipt_operator_review"
    return str(readiness.get("next_smallest_truthful_gap") or "stage17_capability_pack_metadata_receipts")


def _text(value: Any, *, fallback: str = "") -> str:
    text = str(value or "").strip()
    return text or fallback
