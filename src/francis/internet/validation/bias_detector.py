from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

__all__ = ["BiasReport", "BiasDetector"]


@dataclass(frozen=True)
class BiasReport:
    biased: bool
    reason: str


class BiasDetector:
    def detect(self, text: str) -> BiasReport:
        if not isinstance(text, str):
            logger.warning("detect expected text")
            return BiasReport(biased=False, reason="invalid_input")
        return BiasReport(biased=False, reason="no_signals")
