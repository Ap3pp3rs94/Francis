from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["BudgetDecision", "BudgetAllocator"]


@dataclass(frozen=True)
class BudgetDecision:
    allocations: dict[str, float] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


class BudgetAllocator:
    def allocate(self, total_budget: float, demands: dict[str, float]) -> BudgetDecision:
        try:
            total = max(0.0, float(total_budget))
        except (TypeError, ValueError):
            logger.warning("allocate expected numeric total_budget")
            return BudgetDecision()
        if not isinstance(demands, dict) or not demands:
            return BudgetDecision(allocations={})

        requested = sum(float(v) for v in demands.values() if isinstance(v, (int, float)))
        if requested <= 0:
            return BudgetDecision(allocations={})
        scale = min(1.0, total / requested) if total > 0 else 0.0
        allocations = {k: float(v) * scale for k, v in demands.items() if isinstance(v, (int, float))}
        return BudgetDecision(allocations=allocations)
