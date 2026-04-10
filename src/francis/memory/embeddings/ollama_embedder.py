from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

__all__ = ["OllamaEmbedder"]


class OllamaEmbedder:
    name = "ollama"

    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = base_url

    def embed(self, text: str) -> list[float]:
        if not isinstance(text, str) or not text.strip():
            logger.warning("embed expected text")
            return []
        return []
