from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["CorrectionResult", "MisconceptionCorrector"]


@dataclass(frozen=True)
class CorrectionResult:
    corrected: bool
    correction: str
    metadata: dict[str, Any] = field(default_factory=dict)


class MisconceptionCorrector:
    def correct(self, misconception: str) -> CorrectionResult | None:
        if not isinstance(misconception, str) or not misconception.strip():
            logger.warning("correct expected misconception")
            return None
        correction = f"Correction: {misconception.strip()}"
        return CorrectionResult(corrected=True, correction=correction)
