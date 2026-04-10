from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["ExecutionPlan", "ExecutionCoordinator"]


@dataclass(frozen=True)
class ExecutionPlan:
    steps: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class ExecutionCoordinator:
    def coordinate(self, plan: ExecutionPlan) -> bool:
        if not isinstance(plan, ExecutionPlan):
            logger.warning("coordinate expected ExecutionPlan")
            return False
        return True
