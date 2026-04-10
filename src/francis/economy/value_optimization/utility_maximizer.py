from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["UtilityPlan", "UtilityMaximizer"]


@dataclass(frozen=True)
class UtilityPlan:
    choice: str
    utility: float
    metadata: dict[str, Any] = field(default_factory=dict)


class UtilityMaximizer:
    def maximize(self, options: dict[str, float]) -> UtilityPlan | None:
        if not isinstance(options, dict) or not options:
            logger.warning("maximize expected options dict")
            return None
        best = max(options.items(), key=lambda kv: float(kv[1]))
        return UtilityPlan(choice=best[0], utility=float(best[1]))
