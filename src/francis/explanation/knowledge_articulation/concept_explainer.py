from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["ConceptExplanation", "ConceptExplainer"]


@dataclass(frozen=True)
class ConceptExplanation:
    concept: str
    explanation: str
    metadata: dict[str, Any] = field(default_factory=dict)


class ConceptExplainer:
    def explain(self, concept: str) -> ConceptExplanation | None:
        if not isinstance(concept, str) or not concept.strip():
            logger.warning("explain expected concept")
            return None
        explanation = f"{concept.strip()} is a core concept in this domain."
        return ConceptExplanation(concept=concept.strip(), explanation=explanation)
