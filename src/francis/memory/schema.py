from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["MemoryRecord"]


@dataclass(frozen=True)
class MemoryRecord:
    record_id: str
    content: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)
