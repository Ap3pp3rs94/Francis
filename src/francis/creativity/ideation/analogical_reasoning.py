from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["Analogy", "AnalogicalReasoner"]


@dataclass(frozen=True)
class Analogy:
    source: str
    target: str
    bridge: str
    metadata: dict[str, Any] = field(default_factory=dict)


class AnalogicalReasoner:
    def create(self, source: str, target: str) -> Analogy | None:
        if not source or not target:
            logger.warning("create requires source and target")
            return None
        bridge = f"{source} relates to {target}"
        return Analogy(source=source, target=target, bridge=bridge)
