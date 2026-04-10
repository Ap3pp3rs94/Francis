from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

__all__ = ["OpenAIProvider"]


class OpenAIProvider:
    name = "openai"

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key

    def generate(self, prompt: str) -> str:
        if not isinstance(prompt, str) or not prompt.strip():
            logger.warning("generate expected prompt")
            return ""
        return ""
