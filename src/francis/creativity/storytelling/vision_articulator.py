from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["VisionStatement", "VisionArticulator"]


@dataclass(frozen=True)
class VisionStatement:
    statement: str
    metadata: dict[str, Any] = field(default_factory=dict)


class VisionArticulator:
    def articulate(self, theme: str) -> VisionStatement | None:
        if not isinstance(theme, str) or not theme.strip():
            logger.warning("articulate expected non-empty theme")
            return None
        statement = f"Vision: {theme.strip()}"
        return VisionStatement(statement=statement)
