from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["CapabilityRequest", "CapabilityMatch", "CapabilityMatcher"]


@dataclass(frozen=True)
class CapabilityRequest:
    capability: str
    constraints: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CapabilityMatch:
    agent_id: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)


class CapabilityMatcher:
    def __init__(self, registry: dict[str, list[str]] | None = None) -> None:
        self.registry = registry or {}

    def match(self, request: CapabilityRequest) -> list[CapabilityMatch]:
        if not isinstance(request, CapabilityRequest):
            logger.warning("match expected CapabilityRequest")
            return []

        matches: list[CapabilityMatch] = []
        for agent_id, caps in self.registry.items():
            if request.capability in caps:
                matches.append(CapabilityMatch(agent_id=agent_id, score=1.0))

        return sorted(matches, key=lambda m: m.score, reverse=True)
