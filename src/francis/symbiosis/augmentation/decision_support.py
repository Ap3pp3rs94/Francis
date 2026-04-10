from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

__all__ = ["DecisionSupportReport", "DecisionSupport"]


@dataclass(frozen=True)
class DecisionSupportReport:
    recommendation: str


class DecisionSupport:
    def recommend(self, context: str) -> DecisionSupportReport | None:
        if not isinstance(context, str) or not context.strip():
            logger.warning("recommend expected context")
            return None
        return DecisionSupportReport(recommendation="proceed")
