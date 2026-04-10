from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["ReputationEntry", "ReputationSystem"]


@dataclass
class ReputationEntry:
    score: float = 0.0
    events: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class ReputationSystem:
    def __init__(self) -> None:
        self._entries: dict[str, ReputationEntry] = {}

    def update(self, instance_id: str, delta: float, reason: str) -> ReputationEntry | None:
        if not instance_id:
            logger.warning("update expected instance_id")
            return None
        entry = self._entries.get(instance_id, ReputationEntry())
        entry.score = float(entry.score) + float(delta)
        entry.events.append(reason)
        self._entries[instance_id] = entry
        return entry

    def get(self, instance_id: str) -> ReputationEntry | None:
        return self._entries.get(instance_id)
