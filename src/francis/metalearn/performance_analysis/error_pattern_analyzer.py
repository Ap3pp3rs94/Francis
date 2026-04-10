from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

__all__ = ["ErrorPatternReport", "ErrorPatternAnalyzer"]


@dataclass(frozen=True)
class ErrorPatternReport:
    patterns: list[str]


class ErrorPatternAnalyzer:
    def analyze(self, errors: list[str]) -> ErrorPatternReport:
        if not isinstance(errors, list):
            logger.warning("analyze expected errors list")
            return ErrorPatternReport(patterns=[])
        return ErrorPatternReport(patterns=[e for e in errors if e])
