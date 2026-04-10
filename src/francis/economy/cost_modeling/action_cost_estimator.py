from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["ActionCostEstimate", "ActionCostEstimator"]


@dataclass(frozen=True)
class ActionCostEstimate:
    action: str
    cost: float
    metadata: dict[str, Any] = field(default_factory=dict)


class ActionCostEstimator:
    def estimate(self, action: str, base_cost: float = 0.0) -> ActionCostEstimate | None:
        if not isinstance(action, str) or not action.strip():
            logger.warning("estimate expected action")
            return None
        try:
            cost = max(0.0, float(base_cost))
        except (TypeError, ValueError):
            cost = 0.0
        return ActionCostEstimate(action=action.strip(), cost=cost)
