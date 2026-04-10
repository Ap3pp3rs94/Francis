from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["EmergentBehavior"]


@dataclass
class EmergentBehavior:
    signals: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def detect(self) -> list[str]:
        if not self.signals:
            return []
        return [s for s in self.signals if s]
