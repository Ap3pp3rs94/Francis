from __future__ import annotations

import logging
from typing import Protocol

logger = logging.getLogger(__name__)

__all__ = ["EmbeddingModel"]


class EmbeddingModel(Protocol):
    name: str

    def embed(self, text: str) -> list[float]: ...
