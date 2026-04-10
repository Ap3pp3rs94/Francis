from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["WorkloadSnapshot", "WorkloadBalancer"]


@dataclass(frozen=True)
class WorkloadSnapshot:
    loads: dict[str, float] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def lightest_agent(self) -> str | None:
        if not self.loads:
            return None
        return min(self.loads.items(), key=lambda kv: kv[1])[0]


class WorkloadBalancer:
    def __init__(self, baseline: float = 0.0) -> None:
        self.baseline = float(baseline)

    def balance(self, snapshot: WorkloadSnapshot) -> str | None:
        if not isinstance(snapshot, WorkloadSnapshot):
            logger.warning("balance expected WorkloadSnapshot")
            return None
        return snapshot.lightest_agent()
