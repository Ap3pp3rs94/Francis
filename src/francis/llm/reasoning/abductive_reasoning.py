from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

__all__ = ["AbductionResult", "AbductiveReasoner"]


@dataclass(frozen=True)
class AbductionResult:
    hypothesis: str
    confidence: float


class AbductiveReasoner:
    def infer(self, observations: list[str]) -> AbductionResult | None:
        if not isinstance(observations, list) or not observations:
            logger.warning("infer expected observations list")
            return None
        hypothesis = observations[0]
        return AbductionResult(hypothesis=hypothesis, confidence=0.5)
