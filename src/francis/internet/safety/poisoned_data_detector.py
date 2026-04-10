from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

__all__ = ["PoisonedDataReport", "PoisonedDataDetector"]


@dataclass(frozen=True)
class PoisonedDataReport:
    detected: bool
    reason: str


class PoisonedDataDetector:
    def detect(self, text: str) -> PoisonedDataReport:
        if not isinstance(text, str):
            logger.warning("detect expected text")
            return PoisonedDataReport(detected=False, reason="invalid_input")
        return PoisonedDataReport(detected=False, reason="no_signals")
