from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["InterventionPlan", "InterventionPlanner"]


@dataclass(frozen=True)
class InterventionPlan:
    objective: str
    actions: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class InterventionPlanner:
    def plan(self, objective: str) -> InterventionPlan | None:
        if not isinstance(objective, str) or not objective.strip():
            logger.warning("plan expected objective")
            return None
        actions = ["observe", "intervene", "verify"]
        return InterventionPlan(objective=objective.strip(), actions=actions)
