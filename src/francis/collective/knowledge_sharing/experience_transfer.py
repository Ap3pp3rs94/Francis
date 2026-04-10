from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["ExperienceTransfer"]


@dataclass
class ExperienceTransfer:
    source: str
    target: str
    insights: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def transfer(self) -> bool:
        if not self.source or not self.target:
            logger.warning("transfer requires source and target")
            return False
        return True
