from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

__all__ = ["ReplayResult", "DecisionReplay"]


@dataclass(frozen=True)
class ReplayResult:
    replayed: bool
    summary: str


class DecisionReplay:
    def replay(self, decision: str) -> ReplayResult | None:
        if not isinstance(decision, str) or not decision.strip():
            logger.warning("replay expected decision")
            return None
        return ReplayResult(replayed=True, summary=f"Replayed: {decision.strip()}")
