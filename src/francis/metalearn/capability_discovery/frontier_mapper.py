from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

__all__ = ["CapabilityFrontier", "FrontierMapper"]


@dataclass(frozen=True)
class CapabilityFrontier:
    capabilities: list[str] = field(default_factory=list)


class FrontierMapper:
    def map(self, capabilities: list[str]) -> CapabilityFrontier:
        if not isinstance(capabilities, list):
            logger.warning("map expected capabilities list")
            return CapabilityFrontier(capabilities=[])
        return CapabilityFrontier(capabilities=list(capabilities))
