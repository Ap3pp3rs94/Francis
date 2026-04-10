from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

__all__ = ["DomainDriftPrediction", "DomainDriftPredictor"]


@dataclass(frozen=True)
class DomainDriftPrediction:
    drift_risk: float
    reason: str


class DomainDriftPredictor:
    def predict(self, signals: list[float]) -> DomainDriftPrediction:
        if not isinstance(signals, list) or not signals:
            logger.warning("predict expected signals list")
            return DomainDriftPrediction(drift_risk=0.0, reason="no_signals")
        try:
            risk = max(0.0, min(1.0, float(sum(signals) / len(signals))))
        except (TypeError, ValueError):
            risk = 0.0
        return DomainDriftPrediction(drift_risk=risk, reason="aggregate")
