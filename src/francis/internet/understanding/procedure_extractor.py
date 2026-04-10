from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["ProcedureSummary", "ProcedureExtractor"]


@dataclass(frozen=True)
class ProcedureSummary:
    steps: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class ProcedureExtractor:
    def extract(self, text: str) -> ProcedureSummary:
        if not isinstance(text, str):
            logger.warning("extract expected text")
            return ProcedureSummary(steps=[])
        steps = [line.strip() for line in text.splitlines() if line.strip().startswith(("-", "*", "1."))]
        return ProcedureSummary(steps=steps)
