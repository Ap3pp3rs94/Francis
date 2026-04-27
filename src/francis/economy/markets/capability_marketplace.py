from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["CapabilityListing", "CapabilityMarketplace"]


@dataclass(frozen=True)
class CapabilityListing:
    capability: str
    price: float
    metadata: dict[str, Any] = field(default_factory=dict)
    version: str = "0.1.0"
    status: str = "staged"
    risk_tier: str = "normal"
    source: str = "unknown"
    proposal_id: str = ""
    promotion_receipt_id: str = ""
    tests: tuple[str, ...] = ()
    docs: tuple[str, ...] = ()

    def to_catalog_entry(self) -> dict[str, Any]:
        return {
            "capability": _normalized_text(self.capability),
            "version": _normalized_text(self.version, fallback="0.1.0"),
            "status": _normalized_label(self.status),
            "risk_tier": _normalized_label(self.risk_tier, fallback="normal"),
            "source": _normalized_label(self.source),
            "price": float(self.price),
            "proposal_id": _normalized_text(self.proposal_id),
            "promotion_receipt_id": _normalized_text(self.promotion_receipt_id),
            "quality": {
                "tests": list(_to_str_tuple(self.tests)),
                "docs": list(_to_str_tuple(self.docs)),
            },
            "metadata": dict(self.metadata),
        }


def _normalized_text(value: Any, *, fallback: str = "") -> str:
    text = str(value or "").strip()
    return text or fallback


def _normalized_label(value: Any, *, fallback: str = "unknown") -> str:
    return _normalized_text(value, fallback=fallback).lower()


def _to_str_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        text = value.strip()
        return (text,) if text else ()
    if isinstance(value, (list, tuple, set)):
        parts: list[str] = []
        for item in value:
            text = str(item).strip()
            if text:
                parts.append(text)
        return tuple(parts)
    text = str(value).strip()
    return (text,) if text else ()


class CapabilityMarketplace:
    def __init__(self) -> None:
        self._listings: list[CapabilityListing] = []

    def add_listing(self, listing: CapabilityListing) -> None:
        if not isinstance(listing, CapabilityListing):
            logger.warning("add_listing expected CapabilityListing")
            return
        self._listings.append(listing)

    def search(self, capability: str) -> list[CapabilityListing]:
        if not isinstance(capability, str) or not capability.strip():
            return []
        cap = capability.strip()
        return [listing for listing in self._listings if listing.capability == cap]

    def catalog(
        self,
        *,
        status: str | None = None,
        risk_tier: str | None = None,
        source: str | None = None,
    ) -> list[dict[str, Any]]:
        entries = [listing.to_catalog_entry() for listing in self._listings]
        status_filter = _normalized_label(status) if status is not None else ""
        risk_filter = _normalized_label(risk_tier, fallback="normal") if risk_tier is not None else ""
        source_filter = _normalized_label(source) if source is not None else ""

        if status_filter:
            entries = [entry for entry in entries if entry["status"] == status_filter]
        if risk_filter:
            entries = [entry for entry in entries if entry["risk_tier"] == risk_filter]
        if source_filter:
            entries = [entry for entry in entries if entry["source"] == source_filter]
        return sorted(entries, key=lambda entry: (entry["capability"], entry["version"], entry["source"]))

    def summary(self) -> dict[str, Any]:
        entries = self.catalog()
        status_counts: dict[str, int] = {}
        risk_tier_counts: dict[str, int] = {}
        source_counts: dict[str, int] = {}
        tested_count = 0
        documented_count = 0

        for entry in entries:
            _increment(status_counts, entry["status"])
            _increment(risk_tier_counts, entry["risk_tier"])
            _increment(source_counts, entry["source"])
            quality = entry.get("quality") if isinstance(entry.get("quality"), dict) else {}
            if quality.get("tests"):
                tested_count += 1
            if quality.get("docs"):
                documented_count += 1

        return {
            "total": len(entries),
            "status_counts": dict(sorted(status_counts.items())),
            "risk_tier_counts": dict(sorted(risk_tier_counts.items())),
            "source_counts": dict(sorted(source_counts.items())),
            "tested_count": tested_count,
            "documented_count": documented_count,
        }

    # Backward-compatible alias; kept last to avoid shadowing built-in `list`
    # in type annotations above.
    def list(self, listing: CapabilityListing) -> None:  # noqa: A003
        self.add_listing(listing)


def _increment(bucket: dict[str, int], value: Any) -> None:
    label = _normalized_label(value)
    bucket[label] = bucket.get(label, 0) + 1
