from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

__all__ = ["ConfidenceReport", "ConfidenceReporter"]


@dataclass(frozen=True)
class ConfidenceReport:
    confidence: float
    message: str


class ConfidenceReporter:
    def report(self, confidence: float) -> ConfidenceReport:
        try:
            value = max(0.0, min(1.0, float(confidence)))
        except (TypeError, ValueError):
            logger.warning("report expected numeric confidence")
            value = 0.0
        message = "High confidence" if value >= 0.7 else "Low confidence"
        return ConfidenceReport(confidence=value, message=message)
