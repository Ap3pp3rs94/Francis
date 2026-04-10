from __future__ import annotations

import logging
from typing import Protocol

logger = logging.getLogger(__name__)

__all__ = ["ProviderRegistry", "LLMProvider"]


class LLMProvider(Protocol):
    name: str

    def generate(self, prompt: str) -> str: ...


class ProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, LLMProvider] = {}

    def register(self, provider: LLMProvider) -> None:
        name = getattr(provider, "name", None)
        if not isinstance(name, str) or not name.strip():
            logger.warning("register expected provider with name")
            return
        self._providers[name] = provider

    def get(self, name: str) -> LLMProvider | None:
        if not isinstance(name, str) or not name.strip():
            return None
        return self._providers.get(name)

    def list(self) -> list[str]:
        return sorted(self._providers.keys())
