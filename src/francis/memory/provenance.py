from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)

__all__ = ["MemoryProvenance"]


@dataclass(frozen=True)
class MemoryProvenance:
    source: str
    captured_at: datetime = field(default_factory=datetime.utcnow)
