from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

__all__ = ["CapabilityProfile", "CapabilityProfiler"]


@dataclass(frozen=True)
class CapabilityProfile:
    capabilities: list[str]


class CapabilityProfiler:
    def profile(self, capabilities: list[str]) -> CapabilityProfile:
        if not isinstance(capabilities, list):
            logger.warning("profile expected capabilities list")
            return CapabilityProfile(capabilities=[])
        return CapabilityProfile(capabilities=list(capabilities))
