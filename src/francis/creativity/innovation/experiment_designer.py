from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["ExperimentPlan", "ExperimentDesigner"]


@dataclass(frozen=True)
class ExperimentPlan:
    hypothesis: str
    steps: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class ExperimentDesigner:
    def design(self, hypothesis: str) -> ExperimentPlan | None:
        if not hypothesis or not isinstance(hypothesis, str):
            logger.warning("design requires hypothesis")
            return None
        steps = ["define metrics", "run trial", "evaluate results"]
        return ExperimentPlan(hypothesis=hypothesis, steps=steps)
