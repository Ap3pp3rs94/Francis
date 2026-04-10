from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["AestheticScore", "AestheticEvaluator"]


@dataclass(frozen=True)
class AestheticScore:
    score: float
    notes: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class AestheticEvaluator:
    def evaluate(self, text: str) -> AestheticScore:
        if not isinstance(text, str) or not text.strip():
            logger.warning("evaluate expected non-empty text")
            return AestheticScore(score=0.0, notes=["empty"])
        length_score = min(1.0, len(text) / 280.0)
        return AestheticScore(score=length_score, notes=["length_heuristic"])
