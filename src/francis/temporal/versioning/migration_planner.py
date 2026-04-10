from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["MigrationPlan", "MigrationPlanner"]


@dataclass(frozen=True)
class MigrationPlan:
    steps: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class MigrationPlanner:
    def plan(self, from_version: str, to_version: str) -> MigrationPlan | None:
        if not from_version or not to_version:
            logger.warning("plan expected versions")
            return None
        return MigrationPlan(steps=[f"backup {from_version}", f"migrate to {to_version}", "verify"])
