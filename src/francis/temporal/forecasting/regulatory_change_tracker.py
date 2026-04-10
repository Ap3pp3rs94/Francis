from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

__all__ = ["RegulatoryChange", "RegulatoryChangeTracker"]


@dataclass(frozen=True)
class RegulatoryChange:
    summary: str
    impact: str


class RegulatoryChangeTracker:
    def track(self, summary: str, impact: str) -> RegulatoryChange | None:
        if not summary or not impact:
            logger.warning("track expected summary and impact")
            return None
        return RegulatoryChange(summary=summary, impact=impact)
