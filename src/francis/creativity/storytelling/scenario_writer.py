from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["Scenario", "ScenarioWriter"]


@dataclass(frozen=True)
class Scenario:
    premise: str
    outcome: str
    metadata: dict[str, Any] = field(default_factory=dict)


class ScenarioWriter:
    def write(self, premise: str) -> Scenario | None:
        if not isinstance(premise, str) or not premise.strip():
            logger.warning("write expected non-empty premise")
            return None
        outcome = f"Outcome based on: {premise.strip()}"
        return Scenario(premise=premise.strip(), outcome=outcome)
