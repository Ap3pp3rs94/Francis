from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["BisociationPair", "BisociationEngine"]


@dataclass(frozen=True)
class BisociationPair:
    concept_a: str
    concept_b: str
    insight: str
    metadata: dict[str, Any] = field(default_factory=dict)


class BisociationEngine:
    def combine(self, concept_a: str, concept_b: str) -> BisociationPair | None:
        if not concept_a or not concept_b:
            logger.warning("combine requires two concepts")
            return None
        insight = f"{concept_a} meets {concept_b}"
        return BisociationPair(concept_a=concept_a, concept_b=concept_b, insight=insight)
