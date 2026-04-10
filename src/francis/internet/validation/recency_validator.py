from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)

__all__ = ["RecencyReport", "RecencyValidator"]


@dataclass(frozen=True)
class RecencyReport:
    recent: bool
    age_days: float


class RecencyValidator:
    def validate(self, published_at: datetime, max_age_days: int = 365) -> RecencyReport:
        if not isinstance(published_at, datetime):
            logger.warning("validate expected datetime")
            return RecencyReport(recent=False, age_days=0.0)
        age = (datetime.utcnow() - published_at).total_seconds() / 86400.0
        return RecencyReport(recent=age <= max_age_days, age_days=age)
