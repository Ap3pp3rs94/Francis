from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

__all__ = ["BiasCorrectionResult", "BiasCorrection"]


@dataclass(frozen=True)
class BiasCorrectionResult:
    corrected: bool
    message: str


class BiasCorrection:
    def apply(self, text: str) -> BiasCorrectionResult:
        if not isinstance(text, str):
            logger.warning("apply expected text")
            return BiasCorrectionResult(corrected=False, message="invalid_input")
        return BiasCorrectionResult(corrected=True, message="ok")
