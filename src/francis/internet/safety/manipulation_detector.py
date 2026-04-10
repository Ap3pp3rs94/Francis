from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

__all__ = ["ManipulationReport", "ManipulationDetector"]


@dataclass(frozen=True)
class ManipulationReport:
    detected: bool
    reason: str


class ManipulationDetector:
    def detect(self, text: str) -> ManipulationReport:
        if not isinstance(text, str):
            logger.warning("detect expected text")
            return ManipulationReport(detected=False, reason="invalid_input")
        return ManipulationReport(detected=False, reason="no_signals")
