from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

__all__ = ["ConsequenceReport", "ConsequencePredictor"]


@dataclass(frozen=True)
class ConsequenceReport:
    impact: str
    confidence: float


class ConsequencePredictor:
    def predict(self, action: str) -> ConsequenceReport | None:
        if not isinstance(action, str) or not action.strip():
            logger.warning("predict expected action")
            return None
        return ConsequenceReport(impact="unknown", confidence=0.3)
