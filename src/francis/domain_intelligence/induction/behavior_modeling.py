from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["BehaviorModel", "BehaviorModeler"]


@dataclass(frozen=True)
class BehaviorModel:
    behaviors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class BehaviorModeler:
    def build(self, observations: list[str]) -> BehaviorModel:
        if not isinstance(observations, list):
            logger.warning("build expected observations list")
            return BehaviorModel(behaviors=[])
        return BehaviorModel(behaviors=[o for o in observations if o])
