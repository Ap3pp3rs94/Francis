from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

__all__ = ["RoiReport", "RoiCalculator"]


@dataclass(frozen=True)
class RoiReport:
    roi: float


class RoiCalculator:
    def calculate(self, gain: float, cost: float) -> RoiReport:
        try:
            gain_value = float(gain)
            cost_value = float(cost)
        except (TypeError, ValueError):
            logger.warning("calculate expected numeric gain and cost")
            return RoiReport(roi=0.0)
        if cost_value <= 0:
            return RoiReport(roi=0.0)
        return RoiReport(roi=(gain_value - cost_value) / cost_value)
