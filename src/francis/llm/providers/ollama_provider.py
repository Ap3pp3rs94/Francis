from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

__all__ = ["OllamaProvider"]


class OllamaProvider:
    name = "ollama"

    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = base_url

    def generate(self, prompt: str) -> str:
        if not isinstance(prompt, str) or not prompt.strip():
            logger.warning("generate expected prompt")
            return ""
        return ""
