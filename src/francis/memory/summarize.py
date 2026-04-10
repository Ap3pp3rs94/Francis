from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

__all__ = ["MemorySummary", "MemorySummarizer"]


@dataclass(frozen=True)
class MemorySummary:
    summary: str


class MemorySummarizer:
    def summarize(self, text: str) -> MemorySummary:
        if not isinstance(text, str):
            logger.warning("summarize expected text")
            return MemorySummary(summary="")
        return MemorySummary(summary=text.strip()[:200])
