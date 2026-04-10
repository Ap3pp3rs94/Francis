from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

__all__ = ["QdrantStore"]


class QdrantStore:
    name = "qdrant"

    def __init__(self) -> None:
        self._vectors: dict[str, list[float]] = {}

    def upsert(self, record_id: str, vector: list[float]) -> None:
        if not record_id or not isinstance(vector, list):
            logger.warning("upsert expected record_id and vector")
            return
        self._vectors[record_id] = vector

    def query(self, vector: list[float], limit: int = 5) -> list[str]:
        if not isinstance(vector, list):
            return []
        return list(self._vectors.keys())[:limit]
