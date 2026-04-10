from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["ParetoFrontier", "ParetoOptimizer"]


@dataclass(frozen=True)
class ParetoFrontier:
    points: list[dict[str, float]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class ParetoOptimizer:
    def compute(self, candidates: list[dict[str, float]], key: str) -> ParetoFrontier:
        if not isinstance(candidates, list) or not key:
            logger.warning("compute expected candidates and key")
            return ParetoFrontier(points=[])
        sorted_points = sorted(
            [c for c in candidates if isinstance(c, dict) and key in c],
            key=lambda c: float(c.get(key, 0.0)),
            reverse=True,
        )
        return ParetoFrontier(points=sorted_points)
