from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

__all__ = ["UpdateState", "IncrementalUpdate"]


@dataclass(frozen=True)
class UpdateState:
    updated: bool
    reason: str


class IncrementalUpdate:
    def apply(self, payload: object) -> UpdateState:
        if payload is None:
            return UpdateState(updated=False, reason="empty")
        return UpdateState(updated=True, reason="ok")
