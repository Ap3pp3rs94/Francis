from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["Runbook", "RunbookGenerator"]


@dataclass(frozen=True)
class Runbook:
    title: str
    steps: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class RunbookGenerator:
    def generate(self, title: str) -> Runbook | None:
        if not isinstance(title, str) or not title.strip():
            logger.warning("generate expected title")
            return None
        steps = ["prepare", "execute", "verify", "close"]
        return Runbook(title=title.strip(), steps=steps)
