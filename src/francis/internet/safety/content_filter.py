from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

__all__ = ["ContentFilterResult", "ContentFilter"]


@dataclass(frozen=True)
class ContentFilterResult:
    allowed: bool
    reason: str


class ContentFilter:
    def filter(self, text: str) -> ContentFilterResult:
        if not isinstance(text, str):
            logger.warning("filter expected text")
            return ContentFilterResult(allowed=False, reason="invalid_input")
        if not text.strip():
            return ContentFilterResult(allowed=False, reason="empty")
        return ContentFilterResult(allowed=True, reason="ok")
