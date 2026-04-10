from __future__ import annotations

import logging
from dataclasses import dataclass, field

from .schema import MemoryRecord
from .store import MemoryStore

logger = logging.getLogger(__name__)

__all__ = ["RecallResult", "RecallService"]


@dataclass(frozen=True)
class RecallResult:
    records: list[MemoryRecord] = field(default_factory=list)


class RecallService:
    def __init__(self, store: MemoryStore) -> None:
        self.store = store

    def recall_all(self) -> RecallResult:
        if not isinstance(self.store, MemoryStore):
            logger.warning("recall_all expected MemoryStore")
            return RecallResult(records=[])
        return RecallResult(records=self.store.list())
