from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["UsageEvent", "UsageLogger"]


@dataclass(frozen=True)
class UsageEvent:
    credential_id: str
    action: str
    occurred_at: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)


class UsageLogger:
    def __init__(self) -> None:
        self.events: list[UsageEvent] = []

    def log(self, event: UsageEvent) -> None:
        if not isinstance(event, UsageEvent):
            logger.warning("log expected UsageEvent")
            return
        self.events.append(event)

    def recent(self, limit: int = 50) -> list[UsageEvent]:
        if not isinstance(limit, int) or limit <= 0:
            return []
        return list(self.events[-limit:])
