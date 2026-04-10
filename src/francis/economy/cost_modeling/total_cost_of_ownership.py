from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["TotalCostReport", "TotalCostOfOwnership"]


@dataclass(frozen=True)
class TotalCostReport:
    total_cost: float
    components: dict[str, float] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


class TotalCostOfOwnership:
    def calculate(self, components: dict[str, float]) -> TotalCostReport:
        if not isinstance(components, dict):
            logger.warning("calculate expected components dict")
            return TotalCostReport(total_cost=0.0, components={})
        total = sum(float(v) for v in components.values() if isinstance(v, (int, float)))
        return TotalCostReport(total_cost=total, components=dict(components))
