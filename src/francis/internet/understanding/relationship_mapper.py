from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["RelationshipMap", "RelationshipMapper"]


@dataclass(frozen=True)
class RelationshipMap:
    relationships: list[tuple[str, str]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class RelationshipMapper:
    def map(self, entities: list[str]) -> RelationshipMap:
        if not isinstance(entities, list):
            logger.warning("map expected entities list")
            return RelationshipMap(relationships=[])
        relationships = [(entities[i], entities[i + 1]) for i in range(len(entities) - 1)]
        return RelationshipMap(relationships=relationships)
