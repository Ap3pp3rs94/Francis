from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["WorldModel", "WorldModelBuilder"]


@dataclass(frozen=True)
class WorldModel:
    description: str
    assumptions: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class WorldModelBuilder:
    def build(self, description: str) -> WorldModel | None:
        if not isinstance(description, str) or not description.strip():
            logger.warning("build expected description")
            return None
        assumptions = ["baseline stability", "bounded uncertainty"]
        return WorldModel(description=description.strip(), assumptions=assumptions)
