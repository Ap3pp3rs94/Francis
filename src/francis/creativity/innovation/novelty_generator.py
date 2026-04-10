from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["NoveltyResult", "NoveltyGenerator"]


@dataclass(frozen=True)
class NoveltyResult:
    idea: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)


class NoveltyGenerator:
    def generate(self, seed: str) -> NoveltyResult | None:
        if not isinstance(seed, str) or not seed.strip():
            logger.warning("generate expected non-empty seed")
            return None
        idea = f"New angle on {seed.strip()}"
        return NoveltyResult(idea=idea, score=0.5)
