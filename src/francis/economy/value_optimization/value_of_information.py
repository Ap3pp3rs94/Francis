from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

__all__ = ["InformationValue", "ValueOfInformation"]


@dataclass(frozen=True)
class InformationValue:
    value: float


class ValueOfInformation:
    def estimate(self, prior: float, posterior: float) -> InformationValue:
        try:
            prior_value = float(prior)
            posterior_value = float(posterior)
        except (TypeError, ValueError):
            logger.warning("estimate expected numeric inputs")
            return InformationValue(value=0.0)
        return InformationValue(value=max(0.0, posterior_value - prior_value))
