from __future__ import annotations

import logging
from typing import Protocol

logger = logging.getLogger(__name__)

__all__ = ["VectorStore"]


class VectorStore(Protocol):
    name: str

    def upsert(self, record_id: str, vector: list[float]) -> None: ...

    def query(self, vector: list[float], limit: int = 5) -> list[str]: ...
