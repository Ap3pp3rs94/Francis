from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

__all__ = ["CausalResult", "CausalReasoner"]


@dataclass(frozen=True)
class CausalResult:
    cause: str
    effect: str
    confidence: float


class CausalReasoner:
    def infer(self, cause: str, effect: str) -> CausalResult | None:
        if not cause or not effect:
            logger.warning("infer expected cause and effect")
            return None
        return CausalResult(cause=cause, effect=effect, confidence=0.5)
