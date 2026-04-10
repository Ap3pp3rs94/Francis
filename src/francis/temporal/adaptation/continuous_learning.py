from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

__all__ = ["LearningState", "ContinuousLearning"]


@dataclass(frozen=True)
class LearningState:
    enabled: bool
    reason: str


class ContinuousLearning:
    def enable(self, reason: str = "scheduled") -> LearningState:
        return LearningState(enabled=True, reason=reason)

    def disable(self, reason: str = "manual") -> LearningState:
        return LearningState(enabled=False, reason=reason)
