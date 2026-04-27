from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

__all__ = ["analyze_capability_catalog_coherence"]


def analyze_capability_catalog_coherence(entries: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    normalized = [_normalize_entry(entry) for entry in entries]
    normalized = [entry for entry in normalized if entry["capability"]]

    return {
        "total": len(normalized),
        "duplicate_capabilities": _duplicate_capabilities(normalized),
        "duplicate_proposals": _duplicate_proposals(normalized),
        "lineage_gaps": _lineage_gaps(normalized),
        "validation_lineage_gaps": _validation_lineage_gaps(normalized),
        "quality_gaps": _quality_gaps(normalized),
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
    }


def _duplicate_capabilities(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_capability: dict[str, list[dict[str, Any]]] = {}
    for entry in entries:
        by_capability.setdefault(str(entry["capability"]), []).append(entry)

    duplicates: list[dict[str, Any]] = []
    for capability, grouped in sorted(by_capability.items()):
        if len(grouped) < 2:
            continue
        duplicates.append(
            {
                "capability": capability,
                "entries": [_entry_identity(entry) for entry in grouped],
            }
        )
    return duplicates


def _duplicate_proposals(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_proposal: dict[str, set[str]] = {}
    for entry in entries:
        proposal_id = str(entry["proposal_id"])
        if not proposal_id:
            continue
        by_proposal.setdefault(proposal_id, set()).add(str(entry["capability"]))

    duplicates: list[dict[str, Any]] = []
    for proposal_id, capabilities in sorted(by_proposal.items()):
        if len(capabilities) < 2:
            continue
        duplicates.append(
            {
                "proposal_id": proposal_id,
                "capabilities": sorted(capabilities),
            }
        )
    return duplicates


def _lineage_gaps(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    gaps: list[dict[str, Any]] = []
    for entry in entries:
        missing: list[str] = []
        if entry["status"] == "staged" and not entry["proposal_id"]:
            missing.append("proposal_id")
        if entry["status"] == "promoted" and not entry["promotion_receipt_id"]:
            missing.append("promotion_receipt_id")
        if missing:
            gaps.append({**_entry_identity(entry), "missing": missing})
    return gaps


def _validation_lineage_gaps(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    gaps: list[dict[str, Any]] = []
    for entry in entries:
        if entry["source"] not in {"forge", "generated"}:
            continue
        if entry["status"] not in {"staged", "promoted"}:
            continue
        if not entry["validation_receipt_id"]:
            gaps.append({**_entry_identity(entry), "missing": ["validation_receipt_id"]})
    return gaps


def _quality_gaps(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    gaps: list[dict[str, Any]] = []
    for entry in entries:
        missing: list[str] = []
        if not entry["tests"]:
            missing.append("tests")
        if not entry["docs"]:
            missing.append("docs")
        if missing:
            gaps.append({**_entry_identity(entry), "missing": missing})
    return gaps


def _entry_identity(entry: Mapping[str, Any]) -> dict[str, str]:
    return {
        "capability": str(entry.get("capability") or ""),
        "version": str(entry.get("version") or ""),
        "source": str(entry.get("source") or ""),
        "status": str(entry.get("status") or ""),
        "risk_tier": str(entry.get("risk_tier") or ""),
    }


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
