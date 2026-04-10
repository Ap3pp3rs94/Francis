from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

__all__ = ["FactCheckResult", "FactChecker"]


@dataclass(frozen=True)
class FactCheckResult:
    ok: bool
    reason: str


class FactChecker:
    def check(self, claim: str) -> FactCheckResult:
        if not isinstance(claim, str) or not claim.strip():
            logger.warning("check expected claim")
            return FactCheckResult(ok=False, reason="empty_claim")
        return FactCheckResult(ok=True, reason="unverified")
