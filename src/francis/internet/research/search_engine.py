from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

__all__ = ["SearchResult", "SearchEngine"]


@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    snippet: str = ""
    metadata: dict[str, object] = field(default_factory=dict)


class SearchEngine:
    def search(self, query: str, limit: int = 5) -> list[SearchResult]:
        if not isinstance(query, str) or not query.strip():
            logger.warning("search expected query")
            return []
        if not isinstance(limit, int) or limit <= 0:
            return []
        return []
