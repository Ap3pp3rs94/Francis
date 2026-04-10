from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["OutcomeRecord", "OutcomeTracker"]


@dataclass(frozen=True)
class OutcomeRecord:
    operation_id: str
    success: bool
    recorded_at: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)


class OutcomeTracker:
    def __init__(self) -> None:
        self._records: list[OutcomeRecord] = []

    def record(self, record: OutcomeRecord) -> None:
        if not isinstance(record, OutcomeRecord):
            logger.warning("record expected OutcomeRecord")
            return
        self._records.append(record)

    def recent(self, limit: int = 50) -> list[OutcomeRecord]:
        if not isinstance(limit, int) or limit <= 0:
            return []
        return list(self._records[-limit:])
