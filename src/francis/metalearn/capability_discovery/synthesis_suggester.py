from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

__all__ = ["SynthesisSuggestion", "SynthesisSuggester"]


@dataclass(frozen=True)
class SynthesisSuggestion:
    suggestion: str


class SynthesisSuggester:
    def suggest(self, gaps: list[str]) -> list[SynthesisSuggestion]:
        if not isinstance(gaps, list):
            logger.warning("suggest expected gaps list")
            return []
        return [SynthesisSuggestion(suggestion=f"Address {gap}") for gap in gaps if gap]
