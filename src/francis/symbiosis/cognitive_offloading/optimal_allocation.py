from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

__all__ = ["AllocationPlan", "OptimalAllocation"]


@dataclass(frozen=True)
class AllocationPlan:
    ai_tasks: list[str]
    human_tasks: list[str]


class OptimalAllocation:
    def allocate(self, tasks: list[str]) -> AllocationPlan:
        if not isinstance(tasks, list):
            logger.warning("allocate expected tasks list")
            return AllocationPlan(ai_tasks=[], human_tasks=[])
        midpoint = len(tasks) // 2
        return AllocationPlan(ai_tasks=tasks[:midpoint], human_tasks=tasks[midpoint:])
