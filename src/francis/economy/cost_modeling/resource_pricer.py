from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["ResourcePrice", "ResourcePricer"]


@dataclass(frozen=True)
class ResourcePrice:
    resource: str
    unit_cost: float
    metadata: dict[str, Any] = field(default_factory=dict)


class ResourcePricer:
    def price(self, resource: str, unit_cost: float) -> ResourcePrice | None:
        if not isinstance(resource, str) or not resource.strip():
            logger.warning("price expected resource")
            return None
        try:
            cost = max(0.0, float(unit_cost))
        except (TypeError, ValueError):
            cost = 0.0
        return ResourcePrice(resource=resource.strip(), unit_cost=cost)
