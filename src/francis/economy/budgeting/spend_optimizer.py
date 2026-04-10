from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["SpendPlan", "SpendOptimizer"]


@dataclass(frozen=True)
class SpendPlan:
    reductions: dict[str, float] = field(default_factory=dict)
    savings: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


class SpendOptimizer:
    def optimize(self, costs: dict[str, float], target_savings: float) -> SpendPlan:
        if not isinstance(costs, dict):
            logger.warning("optimize expected costs dict")
            return SpendPlan()
        try:
            target = max(0.0, float(target_savings))
        except (TypeError, ValueError):
            target = 0.0
        reductions = {}
        remaining = target
        for key, value in costs.items():
            if remaining <= 0:
                break
            if not isinstance(value, (int, float)):
                continue
            cut = min(float(value), remaining)
            reductions[key] = cut
            remaining -= cut
        saved = target - remaining
        return SpendPlan(reductions=reductions, savings=saved)
