from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["ConceptSummary", "ConceptExtractor"]


@dataclass(frozen=True)
class ConceptSummary:
    concepts: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class ConceptExtractor:
    def extract(self, text: str) -> ConceptSummary:
        if not isinstance(text, str):
            logger.warning("extract expected text")
            return ConceptSummary(concepts=[])
        tokens = [t.strip(".,") for t in text.split() if len(t) > 4]
        concepts = list(dict.fromkeys(tokens))[:10]
        return ConceptSummary(concepts=concepts)
