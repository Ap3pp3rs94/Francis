from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

__all__ = ["SourceCredibilityReport", "SourceCredibilityValidator"]


@dataclass(frozen=True)
class SourceCredibilityReport:
    score: float
    reason: str


class SourceCredibilityValidator:
    def validate(self, source: str) -> SourceCredibilityReport:
        if not isinstance(source, str) or not source.strip():
            logger.warning("validate expected source")
            return SourceCredibilityReport(score=0.0, reason="invalid_input")
        return SourceCredibilityReport(score=0.5, reason="default")
