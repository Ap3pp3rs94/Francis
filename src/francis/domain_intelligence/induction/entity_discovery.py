from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["EntityRecord", "EntityDiscovery"]


@dataclass(frozen=True)
class EntityRecord:
    name: str
    entity_type: str
    metadata: dict[str, Any] = field(default_factory=dict)


class EntityDiscovery:
    def discover(self, text: str) -> list[EntityRecord]:
        if not isinstance(text, str):
            logger.warning("discover expected text")
            return []
        tokens = [t.strip(".,") for t in text.split() if t[:1].isupper()]
        return [EntityRecord(name=t, entity_type="proper_noun") for t in tokens[:10]]
