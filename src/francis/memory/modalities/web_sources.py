from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["WebSourceMemory"]


@dataclass
class WebSourceMemory:
    url: str
    summary: str
    metadata: dict[str, Any] = field(default_factory=dict)
