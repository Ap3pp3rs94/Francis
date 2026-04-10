from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["RevenuePlan", "RevenueMaximizer"]


@dataclass(frozen=True)
class RevenuePlan:
    initiatives: list[str] = field(default_factory=list)
    expected_gain: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


class RevenueMaximizer:
    def plan(self, opportunities: list[str]) -> RevenuePlan:
        if not isinstance(opportunities, list):
            logger.warning("plan expected list opportunities")
            return RevenuePlan()
        initiatives = [o for o in opportunities if o]
        expected_gain = float(len(initiatives)) * 100.0
        return RevenuePlan(initiatives=initiatives, expected_gain=expected_gain)
