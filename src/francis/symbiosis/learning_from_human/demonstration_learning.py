from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

__all__ = ["DemonstrationResult", "DemonstrationLearner"]


@dataclass(frozen=True)
class DemonstrationResult:
    learned: bool
    summary: str


class DemonstrationLearner:
    def learn(self, demonstration: str) -> DemonstrationResult | None:
        if not isinstance(demonstration, str) or not demonstration.strip():
            logger.warning("learn expected demonstration")
            return None
        return DemonstrationResult(learned=True, summary=demonstration.strip())
