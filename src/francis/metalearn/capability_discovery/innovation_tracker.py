from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["InnovationRecord", "InnovationTracker"]


@dataclass(frozen=True)
class InnovationRecord:
    description: str
    recorded_at: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)


class InnovationTracker:
    def __init__(self) -> None:
        self._records: list[InnovationRecord] = []

    def add(self, record: InnovationRecord) -> None:
        if not isinstance(record, InnovationRecord):
            logger.warning("add expected InnovationRecord")
            return
        self._records.append(record)

    def list(self) -> list[InnovationRecord]:
        return list(self._records)
