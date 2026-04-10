from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["PricingResult", "PricingEngine"]


@dataclass(frozen=True)
class PricingResult:
    price: float
    factors: dict[str, float] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


class PricingEngine:
    def price(self, base: float, factors: dict[str, float] | None = None) -> PricingResult:
        try:
            value = max(0.0, float(base))
        except (TypeError, ValueError):
            logger.warning("price expected numeric base")
            value = 0.0
        factors = factors or {}
        adjustment = sum(float(v) for v in factors.values() if isinstance(v, (int, float)))
        return PricingResult(price=value + adjustment, factors=dict(factors))
