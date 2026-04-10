from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

__all__ = ["AttributionRecord", "AttributionModel"]


@dataclass(frozen=True)
class AttributionRecord:
    actor: str
    action: str
    source: str


class AttributionModel:
    def attribute(self, actor: str, action: str, source: str) -> AttributionRecord | None:
        if not actor or not action or not source:
            logger.warning("attribute expected actor, action, source")
            return None
        return AttributionRecord(actor=actor, action=action, source=source)
