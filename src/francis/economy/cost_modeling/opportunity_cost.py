from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

__all__ = ["OpportunityCost", "OpportunityCostCalculator"]


@dataclass(frozen=True)
class OpportunityCost:
    value: float


class OpportunityCostCalculator:
    def calculate(self, best_alternative: float, chosen: float) -> OpportunityCost:
        try:
            value = max(0.0, float(best_alternative) - float(chosen))
        except (TypeError, ValueError):
            logger.warning("calculate expected numeric inputs")
            value = 0.0
        return OpportunityCost(value=value)
