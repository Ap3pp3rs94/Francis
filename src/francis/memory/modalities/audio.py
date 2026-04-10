from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["AudioMemory"]


@dataclass
class AudioMemory:
    transcript: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def summary(self) -> str:
        if not isinstance(self.transcript, str):
            return ""
        return self.transcript.strip()[:200]
