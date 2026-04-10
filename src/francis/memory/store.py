from __future__ import annotations

import logging

from .schema import MemoryRecord

logger = logging.getLogger(__name__)

__all__ = ["MemoryStore"]


class MemoryStore:
    def __init__(self) -> None:
        self._records: dict[str, MemoryRecord] = {}

    def put(self, record: MemoryRecord) -> None:
        if not isinstance(record, MemoryRecord):
            logger.warning("put expected MemoryRecord")
            return
        self._records[record.record_id] = record

    def get(self, record_id: str) -> MemoryRecord | None:
        if not isinstance(record_id, str) or not record_id.strip():
            logger.warning("get expected record_id")
            return None
        return self._records.get(record_id)

    def list(self) -> list[MemoryRecord]:
        return list(self._records.values())
