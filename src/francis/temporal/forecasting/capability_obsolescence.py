from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

__all__ = ["ObsolescenceReport", "CapabilityObsolescence"]


@dataclass(frozen=True)
class ObsolescenceReport:
    obsolescent: bool
    reason: str


class CapabilityObsolescence:
    def assess(self, capability: str, last_used_days: int) -> ObsolescenceReport:
        if not capability:
            logger.warning("assess expected capability")
            return ObsolescenceReport(obsolescent=False, reason="invalid_input")
        try:
            days = int(last_used_days)
        except (TypeError, ValueError):
            days = 0
        obsolescent = days > 365
        return ObsolescenceReport(obsolescent=obsolescent, reason="stale" if obsolescent else "active")
