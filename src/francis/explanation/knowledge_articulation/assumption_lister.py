from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["AssumptionList", "AssumptionLister"]


@dataclass(frozen=True)
class AssumptionList:
    assumptions: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class AssumptionLister:
    def list(self, text: str) -> AssumptionList:
        if not isinstance(text, str) or not text.strip():
            logger.warning("list expected non-empty text")
            return AssumptionList(assumptions=[])
        assumptions = ["context is stable", "inputs are truthful"]
        return AssumptionList(assumptions=assumptions)
