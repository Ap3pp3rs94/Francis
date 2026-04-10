from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["CapabilityProfile", "CapabilitySynthesizer"]


@dataclass(frozen=True)
class CapabilityProfile:
    capabilities: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class CapabilitySynthesizer:
    def synthesize(self, signals: list[str]) -> CapabilityProfile:
        if not isinstance(signals, list):
            logger.warning("synthesize expected signals list")
            return CapabilityProfile(capabilities=[])
        return CapabilityProfile(capabilities=[s for s in signals if s])
