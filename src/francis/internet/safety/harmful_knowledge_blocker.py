from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

__all__ = ["HarmfulKnowledgeResult", "HarmfulKnowledgeBlocker"]


@dataclass(frozen=True)
class HarmfulKnowledgeResult:
    blocked: bool
    reason: str


class HarmfulKnowledgeBlocker:
    def block(self, text: str) -> HarmfulKnowledgeResult:
        if not isinstance(text, str):
            logger.warning("block expected text")
            return HarmfulKnowledgeResult(blocked=True, reason="invalid_input")
        if not text.strip():
            return HarmfulKnowledgeResult(blocked=False, reason="empty")
        return HarmfulKnowledgeResult(blocked=False, reason="no_match")
