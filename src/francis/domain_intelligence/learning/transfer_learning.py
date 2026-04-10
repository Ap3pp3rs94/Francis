from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["TransferLearningPlan", "TransferLearningRunner"]


@dataclass(frozen=True)
class TransferLearningPlan:
    source_domain: str
    target_domain: str
    steps: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class TransferLearningRunner:
    def plan(self, source_domain: str, target_domain: str) -> TransferLearningPlan | None:
        if not source_domain or not target_domain:
            logger.warning("plan requires source and target domain")
            return None
        steps = ["extract features", "map representations", "fine-tune"]
        return TransferLearningPlan(source_domain=source_domain, target_domain=target_domain, steps=steps)

    def run(self, plan: TransferLearningPlan) -> bool:
        if not isinstance(plan, TransferLearningPlan):
            logger.warning("run expected TransferLearningPlan")
            return False
        return True
