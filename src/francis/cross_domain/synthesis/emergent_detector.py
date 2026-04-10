from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["EmergentSignal", "EmergentSignalDetector"]


@dataclass(frozen=True)
class EmergentSignal:
    signal: str
    metadata: dict[str, Any] = field(default_factory=dict)


class EmergentSignalDetector:
    def detect(self, observations: list[str]) -> list[EmergentSignal]:
        if not isinstance(observations, list):
            logger.warning("detect expected list observations")
            return []
        return [EmergentSignal(signal=o) for o in observations if o]
