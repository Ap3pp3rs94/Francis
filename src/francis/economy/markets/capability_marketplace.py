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

    # Backward-compatible alias; kept last to avoid shadowing built-in `list`
    # in type annotations above.
    def list(self, listing: CapabilityListing) -> None:  # noqa: A003
        self.add_listing(listing)
