from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["FinancialPlan", "FinancialPlanner"]


@dataclass(frozen=True)
class FinancialPlan:
    horizon_months: int
    targets: dict[str, float] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


class FinancialPlanner:
    def plan(self, horizon_months: int, targets: dict[str, float]) -> FinancialPlan:
        try:
            horizon = max(1, int(horizon_months))
        except (TypeError, ValueError):
            logger.warning("plan expected numeric horizon_months")
            horizon = 1
        if not isinstance(targets, dict):
            targets = {}
        return FinancialPlan(horizon_months=horizon, targets=dict(targets))
