from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

__all__ = ["ImprovementRecommendation", "ImprovementRecommender"]


@dataclass(frozen=True)
class ImprovementRecommendation:
    recommendation: str


class ImprovementRecommender:
    def recommend(self, reports: list[str]) -> list[ImprovementRecommendation]:
        if not isinstance(reports, list):
            logger.warning("recommend expected reports list")
            return []
        return [ImprovementRecommendation(recommendation=f"Improve {r}") for r in reports if r]
