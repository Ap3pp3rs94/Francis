from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

__all__ = ["DecompositionResult", "Decomposer"]


@dataclass(frozen=True)
class DecompositionResult:
    steps: list[str] = field(default_factory=list)


class Decomposer:
    def decompose(self, task: str) -> DecompositionResult:
        if not isinstance(task, str) or not task.strip():
            logger.warning("decompose expected task")
            return DecompositionResult(steps=[])
        steps = ["understand", "plan", "execute"]
        return DecompositionResult(steps=steps)
