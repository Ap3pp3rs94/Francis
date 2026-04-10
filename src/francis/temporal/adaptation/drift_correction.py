from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

__all__ = ["DriftCorrectionResult", "DriftCorrection"]


@dataclass(frozen=True)
class DriftCorrectionResult:
    corrected: bool
    summary: str


class DriftCorrection:
    def apply(self, drift_level: float) -> DriftCorrectionResult:
        try:
            drift = float(drift_level)
        except (TypeError, ValueError):
            logger.warning("apply expected numeric drift_level")
            return DriftCorrectionResult(corrected=False, summary="invalid_input")
        corrected = drift > 0.0
        return DriftCorrectionResult(corrected=corrected, summary="corrected" if corrected else "no_drift")
