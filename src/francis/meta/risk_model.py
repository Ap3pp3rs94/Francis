from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

__all__ = ["RiskScore", "RiskModel"]


@dataclass(frozen=True)
class RiskScore:
    score: float


class RiskModel:
    def score(self, value: float) -> RiskScore:
        try:
            score_value = max(0.0, min(1.0, float(value)))
        except (TypeError, ValueError):
            logger.warning("score expected numeric value")
            score_value = 0.0
        return RiskScore(score=score_value)
