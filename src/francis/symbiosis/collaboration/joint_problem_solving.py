from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

__all__ = ["JointSolution", "JointProblemSolver"]


@dataclass(frozen=True)
class JointSolution:
    summary: str


class JointProblemSolver:
    def solve(self, problem: str) -> JointSolution | None:
        if not isinstance(problem, str) or not problem.strip():
            logger.warning("solve expected problem")
            return None
        return JointSolution(summary=f"Solved: {problem.strip()}")
