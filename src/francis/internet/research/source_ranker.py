from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

__all__ = ["SourceScore", "SourceRanker"]


@dataclass(frozen=True)
class SourceScore:
    source: str
    score: float


class SourceRanker:
    def rank(self, sources: list[str]) -> list[SourceScore]:
        if not isinstance(sources, list):
            logger.warning("rank expected sources list")
            return []
        scores = [SourceScore(source=s, score=1.0) for s in sources if s]
        return scores
