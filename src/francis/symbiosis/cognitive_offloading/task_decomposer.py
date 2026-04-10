from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

__all__ = ["DecomposedTask", "TaskDecomposer"]


@dataclass(frozen=True)
class DecomposedTask:
    steps: list[str]


class TaskDecomposer:
    def decompose(self, task: str) -> DecomposedTask:
        if not isinstance(task, str) or not task.strip():
            logger.warning("decompose expected task")
            return DecomposedTask(steps=[])
        return DecomposedTask(steps=["analyze", "plan", "execute"])
