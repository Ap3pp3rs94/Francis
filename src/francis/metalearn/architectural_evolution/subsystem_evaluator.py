from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

__all__ = ["SubsystemScore", "SubsystemEvaluator"]


@dataclass(frozen=True)
class SubsystemScore:
    subsystem: str
    score: float


class SubsystemEvaluator:
    def evaluate(self, subsystem: str, score: float) -> SubsystemScore | None:
        if not subsystem:
            logger.warning("evaluate expected subsystem")
            return None
        try:
            value = max(0.0, min(1.0, float(score)))
        except (TypeError, ValueError):
            logger.warning("evaluate expected numeric score")
            value = 0.0
        return SubsystemScore(subsystem=subsystem, score=value)
