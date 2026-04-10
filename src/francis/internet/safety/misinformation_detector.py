from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

__all__ = ["MisinformationReport", "MisinformationDetector"]


@dataclass(frozen=True)
class MisinformationReport:
    flagged: bool
    reason: str


class MisinformationDetector:
    def detect(self, text: str) -> MisinformationReport:
        if not isinstance(text, str):
            logger.warning("detect expected text")
            return MisinformationReport(flagged=False, reason="invalid_input")
        return MisinformationReport(flagged=False, reason="no_signals")
