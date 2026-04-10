from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["ComputeFuture", "ComputeFuturesMarket"]


@dataclass(frozen=True)
class ComputeFuture:
    horizon: str
    price: float
    metadata: dict[str, Any] = field(default_factory=dict)


class ComputeFuturesMarket:
    def quote(self, horizon: str, price: float) -> ComputeFuture | None:
        if not isinstance(horizon, str) or not horizon.strip():
            logger.warning("quote expected horizon")
            return None
        try:
            value = max(0.0, float(price))
        except (TypeError, ValueError):
            value = 0.0
        return ComputeFuture(horizon=horizon.strip(), price=value)
