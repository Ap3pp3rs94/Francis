from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

__all__ = ["UncertaintyReport", "UncertaintyCommunicator"]


@dataclass(frozen=True)
class UncertaintyReport:
    confidence: float
    message: str


class UncertaintyCommunicator:
    def report(self, confidence: float) -> UncertaintyReport:
        try:
            value = max(0.0, min(1.0, float(confidence)))
        except (TypeError, ValueError):
            logger.warning("report expected numeric confidence")
            value = 0.0
        message = "High confidence" if value >= 0.7 else "Low confidence"
        return UncertaintyReport(confidence=value, message=message)
