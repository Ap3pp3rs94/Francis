from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["ArchitectureProposal", "ArchitectureProposer"]


@dataclass(frozen=True)
class ArchitectureProposal:
    title: str
    summary: str
    metadata: dict[str, Any] = field(default_factory=dict)


class ArchitectureProposer:
    def propose(self, goal: str) -> ArchitectureProposal | None:
        if not isinstance(goal, str) or not goal.strip():
            logger.warning("propose expected goal")
            return None
        summary = f"Proposal for {goal.strip()}"
        return ArchitectureProposal(title=goal.strip(), summary=summary)
