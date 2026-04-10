from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["StructuredMemory"]


@dataclass
class StructuredMemory:
    data: dict[str, Any] = field(default_factory=dict)

    def keys(self) -> list[str]:
        return list(self.data.keys())
