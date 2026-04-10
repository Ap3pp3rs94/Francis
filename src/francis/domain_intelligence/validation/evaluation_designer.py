from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["EvaluationPlan", "EvaluationPlanner"]


@dataclass(frozen=True)
class EvaluationPlan:
    goals: list[str] = field(default_factory=list)
    metrics: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class EvaluationPlanner:
    def plan(self, goals: list[str]) -> EvaluationPlan:
        if not isinstance(goals, list) or not goals:
            logger.warning("plan expected goals list")
            return EvaluationPlan(goals=[], metrics=[])
        metrics = ["accuracy", "latency"]
        return EvaluationPlan(goals=list(goals), metrics=metrics)
