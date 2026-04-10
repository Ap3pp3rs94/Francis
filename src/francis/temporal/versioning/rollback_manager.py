from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

__all__ = ["RollbackResult", "RollbackManager"]


@dataclass(frozen=True)
class RollbackResult:
    rolled_back: bool
    reason: str


class RollbackManager:
    def rollback(self, to_version: str) -> RollbackResult | None:
        if not to_version:
            logger.warning("rollback expected to_version")
            return None
        return RollbackResult(rolled_back=True, reason=f"rolled back to {to_version}")
