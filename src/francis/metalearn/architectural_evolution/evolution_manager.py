from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["EvolutionResult", "EvolutionManager"]


@dataclass(frozen=True)
class EvolutionResult:
    evolved: bool
    summary: str
    metadata: dict[str, Any] = field(default_factory=dict)


class EvolutionManager:
    def evolve(self, proposal: str) -> EvolutionResult:
        if not isinstance(proposal, str) or not proposal.strip():
            logger.warning("evolve expected proposal")
            return EvolutionResult(evolved=False, summary="invalid_input")
        return EvolutionResult(evolved=True, summary=f"Evolved: {proposal.strip()}")
