from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

__all__ = ["UpdateOutcome", "PostActionUpdate"]


@dataclass(frozen=True)
class UpdateOutcome:
    updated: bool
    reason: str


class PostActionUpdate:
    def apply(self, success: bool, notes: str | None = None) -> UpdateOutcome:
        if not isinstance(success, bool):
            logger.warning("apply expected bool success")
            return UpdateOutcome(updated=False, reason="invalid_input")
        reason = notes or ("success" if success else "failed")
        return UpdateOutcome(updated=True, reason=reason)
