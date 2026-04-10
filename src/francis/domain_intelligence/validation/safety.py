from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

__all__ = ["SafetyAssessment", "SafetyChecker"]


@dataclass(frozen=True)
class SafetyAssessment:
    safe: bool
    reason: str


class SafetyChecker:
    def assess(self, risk_level: float) -> SafetyAssessment:
        try:
            risk = float(risk_level)
        except (TypeError, ValueError):
            logger.warning("assess expected numeric risk_level")
            return SafetyAssessment(safe=False, reason="invalid_input")
        return SafetyAssessment(safe=risk < 0.7, reason="ok" if risk < 0.7 else "high_risk")
