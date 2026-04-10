from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

__all__ = ["ActiveLearningResult", "ActiveLearningLoop"]


@dataclass(frozen=True)
class ActiveLearningResult:
    selected: list[int]


class ActiveLearningLoop:
    def select(self, scores: list[float], k: int = 5) -> ActiveLearningResult:
        if not isinstance(scores, list) or k <= 0:
            logger.warning("select expected scores list and positive k")
            return ActiveLearningResult(selected=[])
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        return ActiveLearningResult(selected=ranked[:k])
