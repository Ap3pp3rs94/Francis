from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

__all__ = ["ConstraintFinding", "ConstraintDiscovery"]


@dataclass(frozen=True)
class ConstraintFinding:
    constraint: str


class ConstraintDiscovery:
    def discover(self, text: str) -> list[ConstraintFinding]:
        if not isinstance(text, str) or not text.strip():
            logger.warning("discover expected text")
            return []
        return [ConstraintFinding(constraint="time"), ConstraintFinding(constraint="budget")]
