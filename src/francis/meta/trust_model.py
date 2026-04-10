from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

__all__ = ["TrustScore", "TrustModel"]


@dataclass(frozen=True)
class TrustScore:
    score: float


class TrustModel:
    def score(self, value: float) -> TrustScore:
        try:
            score_value = max(0.0, min(1.0, float(value)))
        except (TypeError, ValueError):
            logger.warning("score expected numeric value")
            score_value = 0.0
        return TrustScore(score=score_value)
