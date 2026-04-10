from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["ImageMemory"]


@dataclass
class ImageMemory:
    description: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def summary(self) -> str:
        if not isinstance(self.description, str):
            return ""
        return self.description.strip()[:200]
