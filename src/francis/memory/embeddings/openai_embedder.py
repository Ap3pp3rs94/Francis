from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

__all__ = ["OpenAIEmbedder"]


class OpenAIEmbedder:
    name = "openai"

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key

    def embed(self, text: str) -> list[float]:
        if not isinstance(text, str) or not text.strip():
            logger.warning("embed expected text")
            return []
        return []
