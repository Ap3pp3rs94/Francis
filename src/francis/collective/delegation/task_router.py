from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["TaskRoute", "TaskRouter"]


@dataclass(frozen=True)
class TaskRoute:
    task_id: str
    agent_id: str
    metadata: dict[str, Any] = field(default_factory=dict)


class TaskRouter:
    def __init__(self, default_agent: str = "local") -> None:
        self.default_agent = default_agent

    def route(self, task_id: str, candidates: list[str] | None = None) -> TaskRoute | None:
        if not isinstance(task_id, str) or not task_id.strip():
            logger.warning("route expected non-empty task_id")
            return None
        chosen = self.default_agent
        if candidates:
            chosen = candidates[0]
        return TaskRoute(task_id=task_id, agent_id=chosen)
