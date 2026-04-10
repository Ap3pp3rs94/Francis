from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

__all__ = ["ConfidenceReport", "ConfidenceCalibrator"]


@dataclass(frozen=True)
class ConfidenceReport:
    calibrated: bool
    confidence: float


class ConfidenceCalibrator:
    def calibrate(self, raw_confidence: float) -> ConfidenceReport:
        try:
            value = float(raw_confidence)
        except (TypeError, ValueError):
            logger.warning("calibrate expected numeric confidence")
            return ConfidenceReport(calibrated=False, confidence=0.0)
        value = max(0.0, min(1.0, value))
        return ConfidenceReport(calibrated=True, confidence=value)
