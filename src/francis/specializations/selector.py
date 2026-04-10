from __future__ import annotations

import logging
from dataclasses import dataclass

from .registry import SpecializationRegistry

logger = logging.getLogger(__name__)

__all__ = ["SelectionResult", "SpecializationSelector"]


@dataclass(frozen=True)
class SelectionResult:
    name: str
    reason: str


class SpecializationSelector:
    def __init__(self, registry: SpecializationRegistry) -> None:
        self.registry = registry

    def select(self, capability: str) -> SelectionResult | None:
        if not isinstance(capability, str) or not capability.strip():
            logger.warning("select expected capability")
            return None
        for name in self.registry.list():
            if capability in name:
                return SelectionResult(name=name, reason="name_match")
        return None
