from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

__all__ = ["ScenarioResult", "ScenarioGenerator"]


@dataclass(frozen=True)
class ScenarioResult:
    scenario: str


class ScenarioGenerator:
    def generate(self, prompt: str) -> ScenarioResult | None:
        if not isinstance(prompt, str) or not prompt.strip():
            logger.warning("generate expected prompt")
            return None
        return ScenarioResult(scenario=f"Scenario: {prompt.strip()}")
