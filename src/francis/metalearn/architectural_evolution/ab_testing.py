from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["AbTestPlan", "AbTester"]


@dataclass(frozen=True)
class AbTestPlan:
    variant_a: str
    variant_b: str
    metric: str
    metadata: dict[str, Any] = field(default_factory=dict)


class AbTester:
    def plan(self, variant_a: str, variant_b: str, metric: str) -> AbTestPlan | None:
        if not variant_a or not variant_b or not metric:
            logger.warning("plan expected variants and metric")
            return None
        return AbTestPlan(variant_a=variant_a, variant_b=variant_b, metric=metric)
