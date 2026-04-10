from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["ExtractedContent", "ContentExtractor"]


@dataclass(frozen=True)
class ExtractedContent:
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


class ContentExtractor:
    def extract(self, raw: str) -> ExtractedContent:
        if not isinstance(raw, str):
            logger.warning("extract expected raw string")
            return ExtractedContent(text="")
        text = raw.strip()
        return ExtractedContent(text=text)
