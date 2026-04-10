from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["DocumentParseResult", "DocumentParser"]


@dataclass(frozen=True)
class DocumentParseResult:
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


class DocumentParser:
    def parse(self, content: str) -> DocumentParseResult:
        if not isinstance(content, str):
            logger.warning("parse expected content")
            return DocumentParseResult(text="")
        return DocumentParseResult(text=content.strip())
