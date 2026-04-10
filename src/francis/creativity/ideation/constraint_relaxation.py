from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["ConstraintSet", "ConstraintRelaxer"]


@dataclass(frozen=True)
class ConstraintSet:
    rules: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class ConstraintRelaxer:
    def relax(self, constraints: ConstraintSet, count: int = 1) -> ConstraintSet:
        if not isinstance(constraints, ConstraintSet):
            logger.warning("relax expected ConstraintSet")
            return ConstraintSet()
        if count <= 0:
            return constraints
        relaxed = list(constraints.rules[:-count]) if constraints.rules else []
        return ConstraintSet(rules=relaxed, metadata=dict(constraints.metadata))
