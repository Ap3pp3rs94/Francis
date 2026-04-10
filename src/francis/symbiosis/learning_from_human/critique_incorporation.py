from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

__all__ = ["CritiqueResult", "CritiqueIncorporator"]


@dataclass(frozen=True)
class CritiqueResult:
    incorporated: bool
    summary: str


class CritiqueIncorporator:
    def incorporate(self, critique: str) -> CritiqueResult | None:
        if not isinstance(critique, str) or not critique.strip():
            logger.warning("incorporate expected critique")
            return None
        return CritiqueResult(incorporated=True, summary=critique.strip())
