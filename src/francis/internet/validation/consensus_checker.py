from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

__all__ = ["ConsensusReport", "ConsensusChecker"]


@dataclass(frozen=True)
class ConsensusReport:
    consensus: bool
    reason: str


class ConsensusChecker:
    def check(self, sources: list[str]) -> ConsensusReport:
        if not isinstance(sources, list):
            logger.warning("check expected sources list")
            return ConsensusReport(consensus=False, reason="invalid_input")
        if len(set(sources)) <= 1:
            return ConsensusReport(consensus=True, reason="single_source")
        return ConsensusReport(consensus=False, reason="mixed_sources")
