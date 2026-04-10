from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

__all__ = ["CurriculumResult", "CurriculumOptimizer"]


@dataclass(frozen=True)
class CurriculumResult:
    ordered: list[str]


class CurriculumOptimizer:
    def optimize(self, topics: list[str]) -> CurriculumResult:
        if not isinstance(topics, list):
            logger.warning("optimize expected topics list")
            return CurriculumResult(ordered=[])
        return CurriculumResult(ordered=list(topics))
