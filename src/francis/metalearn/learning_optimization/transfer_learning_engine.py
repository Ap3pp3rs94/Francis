from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

__all__ = ["TransferLearningOutcome", "TransferLearningEngine"]


@dataclass(frozen=True)
class TransferLearningOutcome:
    transferred: bool
    summary: str


class TransferLearningEngine:
    def transfer(self, source: str, target: str) -> TransferLearningOutcome | None:
        if not source or not target:
            logger.warning("transfer expected source and target")
            return None
        return TransferLearningOutcome(transferred=True, summary=f"{source} -> {target}")
