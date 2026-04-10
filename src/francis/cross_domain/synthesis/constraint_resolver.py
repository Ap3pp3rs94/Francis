from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["ConstraintSolution", "ConstraintResolver"]


@dataclass(frozen=True)
class ConstraintSolution:
    resolved: bool
    actions: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class ConstraintResolver:
    def resolve(self, constraints: list[str]) -> ConstraintSolution:
        if not isinstance(constraints, list):
            logger.warning("resolve expected list constraints")
            return ConstraintSolution(resolved=False, actions=[])
        if not constraints:
            return ConstraintSolution(resolved=True, actions=["no_constraints"])
        return ConstraintSolution(resolved=True, actions=[f"relax {constraints[0]}"])
