from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

__all__ = ["VerificationResult", "FactVerifier"]


@dataclass(frozen=True)
class VerificationResult:
    verified: bool
    reason: str


class FactVerifier:
    def verify(self, claim: str) -> VerificationResult:
        if not isinstance(claim, str) or not claim.strip():
            logger.warning("verify expected claim")
            return VerificationResult(verified=False, reason="empty_claim")
        return VerificationResult(verified=False, reason="unverified")
