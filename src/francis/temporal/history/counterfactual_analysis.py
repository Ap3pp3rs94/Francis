from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

__all__ = ["CounterfactualOutcome", "CounterfactualAnalysis"]


@dataclass(frozen=True)
class CounterfactualOutcome:
    scenario: str
    outcome: str


class CounterfactualAnalysis:
    def analyze(self, scenario: str) -> CounterfactualOutcome | None:
        if not isinstance(scenario, str) or not scenario.strip():
            logger.warning("analyze expected scenario")
            return None
        return CounterfactualOutcome(scenario=scenario, outcome="unknown")
