from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["CounterfactualResult", "CounterfactualExplainer"]


@dataclass(frozen=True)
class CounterfactualResult:
    original: str
    counterfactual: str
    metadata: dict[str, Any] = field(default_factory=dict)


class CounterfactualExplainer:
    def explain(self, original: str, alternative: str) -> CounterfactualResult | None:
        if not original or not alternative:
            logger.warning("explain requires original and alternative")
            return None
        return CounterfactualResult(original=original, counterfactual=alternative)
