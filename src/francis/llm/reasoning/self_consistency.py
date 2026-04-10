from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

__all__ = ["SelfConsistencyReport", "SelfConsistencyChecker"]


@dataclass(frozen=True)
class SelfConsistencyReport:
    consistent: bool
    reason: str


class SelfConsistencyChecker:
    def check(self, samples: list[str]) -> SelfConsistencyReport:
        if not isinstance(samples, list) or not samples:
            logger.warning("check expected samples list")
            return SelfConsistencyReport(consistent=False, reason="no_samples")
        consensus = len(set(samples)) == 1
        return SelfConsistencyReport(consistent=consensus, reason="consensus" if consensus else "divergent")
