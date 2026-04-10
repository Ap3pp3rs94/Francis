from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

__all__ = ["CapabilityGap", "GapIdentifier"]


@dataclass(frozen=True)
class CapabilityGap:
    missing: str


class GapIdentifier:
    def identify(self, expected: list[str], actual: list[str]) -> list[CapabilityGap]:
        if not isinstance(expected, list) or not isinstance(actual, list):
            logger.warning("identify expected lists")
            return []
        gaps = [CapabilityGap(missing=item) for item in expected if item not in actual]
        return gaps
