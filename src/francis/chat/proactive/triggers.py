from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["TriggerType", "ProactiveTrigger", "evaluate_triggers"]


class TriggerType(Enum):
    TIME = "time"
    EVENT = "event"
    SAFETY = "safety"


@dataclass(frozen=True)
class ProactiveTrigger:
    trigger_type: TriggerType
    reason: str
    priority: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "trigger_type": self.trigger_type.value,
            "reason": self.reason,
            "priority": self.priority,
            "metadata": dict(self.metadata or {}),
        }


def evaluate_triggers(context: dict[str, Any] | None = None) -> list[ProactiveTrigger]:
    if context is None:
        context = {}
    if not isinstance(context, dict):
        logger.warning("evaluate_triggers expected dict context")
        context = {}

    triggers: list[ProactiveTrigger] = []

    if context.get("safety_alert"):
        triggers.append(
            ProactiveTrigger(
                trigger_type=TriggerType.SAFETY,
                reason="safety_alert",
                priority=10,
                metadata={"source": context.get("source", "unknown")},
            )
        )

    if context.get("missed_checkin"):
        triggers.append(
            ProactiveTrigger(
                trigger_type=TriggerType.TIME,
                reason="missed_checkin",
                priority=5,
            )
        )

    if context.get("event"):
        triggers.append(
            ProactiveTrigger(
                trigger_type=TriggerType.EVENT,
                reason=str(context.get("event")),
                priority=int(context.get("priority", 1)),
            )
        )

    return sorted(triggers, key=lambda t: t.priority, reverse=True)
