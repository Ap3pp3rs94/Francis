from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["ProactiveGoal", "goals_to_messages"]


@dataclass(frozen=True)
class ProactiveGoal:
    description: str
    urgency: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "description": self.description,
            "urgency": self.urgency,
            "metadata": dict(self.metadata or {}),
        }


def goals_to_messages(goals: list[ProactiveGoal], max_messages: int = 3) -> list[str]:
    if not isinstance(goals, list):
        logger.warning("goals_to_messages expected list of ProactiveGoal")
        return []
    if not isinstance(max_messages, int) or max_messages <= 0:
        logger.warning("max_messages must be a positive int")
        return []

    ordered = sorted(goals, key=lambda g: g.urgency, reverse=True)
    messages: list[str] = []
    for goal in ordered:
        if not isinstance(goal, ProactiveGoal):
            continue
        text = str(goal.description).strip()
        if not text:
            continue
        messages.append(text)
        if len(messages) >= max_messages:
            break

    return messages
