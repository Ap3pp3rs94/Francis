from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["OperationPlan", "OperationPlanner"]


@dataclass(frozen=True)
class OperationPlan:
    objective: str
    steps: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class OperationPlanner:
    def plan(self, objective: str) -> OperationPlan | None:
        if not isinstance(objective, str) or not objective.strip():
            logger.warning("plan expected objective")
            return None
        steps = ["assess", "execute", "validate"]
        return OperationPlan(objective=objective.strip(), steps=steps)
