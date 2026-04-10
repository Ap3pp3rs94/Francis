from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["MetaphorResult", "MetaphorGenerator"]


@dataclass(frozen=True)
class MetaphorResult:
    metaphor: str
    metadata: dict[str, Any] = field(default_factory=dict)


class MetaphorGenerator:
    def generate(self, topic: str) -> MetaphorResult | None:
        if not isinstance(topic, str) or not topic.strip():
            logger.warning("generate expected non-empty topic")
            return None
        metaphor = f"{topic.strip()} is like a compass in the dark"
        return MetaphorResult(metaphor=metaphor)
