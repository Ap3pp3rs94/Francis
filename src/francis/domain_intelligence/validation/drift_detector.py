from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

__all__ = ["DriftReport", "DriftDetector"]


@dataclass(frozen=True)
class DriftReport:
    drifted: bool
    score: float


class DriftDetector:
    def detect(self, baseline: float, current: float, threshold: float = 0.1) -> DriftReport:
        try:
            delta = abs(float(current) - float(baseline))
        except (TypeError, ValueError):
            logger.warning("detect expected numeric inputs")
            return DriftReport(drifted=False, score=0.0)
        drifted = delta > float(threshold)
        return DriftReport(drifted=drifted, score=delta)
