from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

__all__ = ["VerificationOutcome", "FormalVerifier"]


@dataclass(frozen=True)
class VerificationOutcome:
    verified: bool
    reason: str


class FormalVerifier:
    def verify(self, statement: str) -> VerificationOutcome:
        if not isinstance(statement, str) or not statement.strip():
            logger.warning("verify expected statement")
            return VerificationOutcome(verified=False, reason="invalid_input")
        return VerificationOutcome(verified=False, reason="unproven")
