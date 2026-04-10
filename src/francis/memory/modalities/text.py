from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["TextMemory"]


@dataclass
class TextMemory:
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def summarize(self) -> str:
        if not isinstance(self.content, str):
            return ""
        return self.content.strip()[:200]
