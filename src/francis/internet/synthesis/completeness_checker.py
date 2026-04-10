from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

__all__ = ["CompletenessReport", "CompletenessChecker"]


@dataclass(frozen=True)
class CompletenessReport:
    complete: bool
    coverage: float


class CompletenessChecker:
    def check(self, items: list[str], required: list[str]) -> CompletenessReport:
        if not isinstance(items, list) or not isinstance(required, list):
            logger.warning("check expected lists")
            return CompletenessReport(complete=False, coverage=0.0)
        if not required:
            return CompletenessReport(complete=True, coverage=1.0)
        found = sum(1 for r in required if r in items)
        coverage = found / len(required)
        return CompletenessReport(complete=coverage >= 1.0, coverage=coverage)
