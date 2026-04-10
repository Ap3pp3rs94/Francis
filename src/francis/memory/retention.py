from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

__all__ = ["RetentionPolicy", "RetentionResult", "apply_retention"]


@dataclass(frozen=True)
class RetentionPolicy:
    max_records: int = 1000


@dataclass(frozen=True)
class RetentionResult:
    kept: int
    dropped: int


def apply_retention(count: int, policy: RetentionPolicy) -> RetentionResult:
    if not isinstance(count, int) or count < 0:
        logger.warning("apply_retention expected non-negative count")
        return RetentionResult(kept=0, dropped=0)
    max_records = max(0, int(policy.max_records))
    kept = min(count, max_records)
    dropped = max(0, count - kept)
    return RetentionResult(kept=kept, dropped=dropped)
