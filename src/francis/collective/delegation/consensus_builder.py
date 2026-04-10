from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["ConsensusDecision", "ConsensusBuilder"]


@dataclass(frozen=True)
class ConsensusDecision:
    accepted: bool
    votes: dict[str, bool] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


class ConsensusBuilder:
    def __init__(self, quorum: int = 1) -> None:
        self.quorum = max(1, int(quorum))

    def decide(self, votes: dict[str, bool]) -> ConsensusDecision:
        if not isinstance(votes, dict):
            logger.warning("decide expected dict votes")
            return ConsensusDecision(accepted=False, votes={})

        yes_votes = sum(1 for v in votes.values() if v)
        accepted = yes_votes >= self.quorum
        return ConsensusDecision(accepted=accepted, votes=votes)
