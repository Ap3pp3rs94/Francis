from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["FeasibilityReport", "FeasibilityChecker"]


@dataclass(frozen=True)
class FeasibilityReport:
    feasible: bool
    reasons: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class FeasibilityChecker:
    def check(self, idea: str) -> FeasibilityReport:
        if not isinstance(idea, str) or not idea.strip():
            logger.warning("check expected non-empty idea")
            return FeasibilityReport(feasible=False, reasons=["empty"])
        return FeasibilityReport(feasible=True, reasons=["basic_checks_passed"])
