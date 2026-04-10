from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["CompositeScore", "CompositeEvaluator"]


@dataclass(frozen=True)
class CompositeScore:
    score: float
    components: dict[str, float] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


class CompositeEvaluator:
    def evaluate(self, metrics: dict[str, float]) -> CompositeScore:
        if not isinstance(metrics, dict) or not metrics:
            logger.warning("evaluate expected metrics dict")
            return CompositeScore(score=0.0, components={})
        values = [float(v) for v in metrics.values()]
        score = sum(values) / len(values)
        return CompositeScore(score=score, components=dict(metrics))
