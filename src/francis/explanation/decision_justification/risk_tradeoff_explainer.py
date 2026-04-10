from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["RiskTradeoff", "RiskTradeoffExplainer"]


@dataclass(frozen=True)
class RiskTradeoff:
    choice: str
    risk: float
    benefit: float
    metadata: dict[str, Any] = field(default_factory=dict)


class RiskTradeoffExplainer:
    def explain(self, choice: str, risk: float, benefit: float) -> RiskTradeoff | None:
        if not choice:
            logger.warning("explain expected choice")
            return None
        try:
            risk_value = float(risk)
            benefit_value = float(benefit)
        except (TypeError, ValueError):
            logger.warning("explain expected numeric risk/benefit")
            return None
        return RiskTradeoff(choice=choice, risk=risk_value, benefit=benefit_value)
