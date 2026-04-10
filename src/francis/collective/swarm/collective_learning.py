from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["CollectiveLearning"]


@dataclass
class CollectiveLearning:
    observations: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_observation(self, observation: str) -> None:
        if not isinstance(observation, str) or not observation.strip():
            logger.warning("add_observation expected non-empty string")
            return
        self.observations.append(observation.strip())
