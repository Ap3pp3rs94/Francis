from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["EvidenceCitation", "EvidenceCiter"]


@dataclass(frozen=True)
class EvidenceCitation:
    source: str
    excerpt: str
    metadata: dict[str, Any] = field(default_factory=dict)


class EvidenceCiter:
    def cite(self, source: str, excerpt: str) -> EvidenceCitation | None:
        if not source or not excerpt:
            logger.warning("cite expected source and excerpt")
            return None
        return EvidenceCitation(source=str(source), excerpt=str(excerpt))
